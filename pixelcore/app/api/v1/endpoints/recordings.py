"""
Recording upload, download and deletion endpoints.
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.task_runner import enqueue_task_with_fallback
from app.models.interview import Interview, InterviewInterviewer
from app.models.user import User, UserRole
from app.schemas import RecordingUploadResponse
from app.services.access_policy import AccessPolicy
from app.services.idempotency_service import check_idempotency, store_idempotency_response
from app.services.recording_service import process_recording_metadata
from app.tasks.recording_tasks import process_recording_metadata_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recordings", tags=["recordings"])

_RECORDINGS_DIR = Path("recordings")
_MAX_BYTES = 500 * 1024 * 1024
_ALLOWED_MIME = {"video/webm", "video/mp4", "video/x-matroska", "application/octet-stream"}
_CHUNK = 1024 * 1024  # 1 MB chunks for streaming


def _range_response(request: Request, path: Path, token: str):
    """Serve a video file with HTTP Range support for seeking."""
    file_size = path.stat().st_size
    media = "video/webm" if path.suffix == ".webm" else "video/mp4"
    filename = f"interview_{token[:8]}{path.suffix}"

    range_header = request.headers.get("range")
    if not range_header:
        # Full file response
        return FileResponse(
            str(path), media_type=media, filename=filename,
            headers={"Accept-Ranges": "bytes"},
        )

    # Parse "bytes=start-end"
    try:
        unit, ranges = range_header.split("=", 1)
        start_str, end_str = ranges.strip().split("-", 1)
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except (ValueError, AttributeError):
        raise HTTPException(416, "Invalid Range header")

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(416, "Range not satisfiable")

    length = end - start + 1

    def _iter():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        _iter(),
        status_code=206,
        media_type=media,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


async def _get_interview(token: str, db: AsyncSession) -> Interview:
    res = await db.execute(
        select(Interview)
        .options(
            selectinload(Interview.interviewers).selectinload(InterviewInterviewer.interviewer),
            selectinload(Interview.hr),
            selectinload(Interview.candidate),
        )
        .where(Interview.access_token == token)
    )
    iv = res.scalar_one_or_none()
    if not iv:
        raise HTTPException(404, "Interview not found")
    return iv


@router.post("/upload/{interview_token}", response_model=RecordingUploadResponse)
async def upload_recording(
    interview_token: str,
    file: UploadFile = File(...),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_interview(interview_token, db)
    AccessPolicy.ensure_candidate_owner(iv, current_user, "Only the candidate can upload recordings")

    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    if ct not in _ALLOWED_MIME and not any(fn.endswith(e) for e in (".webm", ".mp4", ".mkv")):
        raise HTTPException(400, "Unsupported media format")

    idem_record, cached = await check_idempotency(
        db, "record", x_idempotency_key,
        {"interview_token": interview_token, "filename": file.filename, "content_type": ct},
    )
    if cached:
        return RecordingUploadResponse.model_validate(cached)

    _RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".webm" if "webm" in (ct + fn) else ".mp4"
    dest = _RECORDINGS_DIR / f"interview_{iv.id}{ext}"

    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Recording exceeds 500 MB")
            f.write(chunk)

    iv.recording_url = str(dest)
    iv.recording_size_bytes = size
    await db.flush()

    await enqueue_task_with_fallback(
        process_recording_metadata_task,
        payload={"recording_path": str(dest), "size_bytes": size},
        fallback_callable=lambda: process_recording_metadata(str(dest), size),
        endpoint_name="/recordings/upload",
    )

    resp = RecordingUploadResponse(
        success=True, recording_url=str(dest), size_bytes=size, message="Saved"
    )
    await store_idempotency_response(db, idem_record, resp.model_dump(mode="json"))
    return resp


@router.get("/download/{interview_token}")
async def download_recording(
    interview_token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_interview(interview_token, db)
    if current_user.role == UserRole.CANDIDATE:
        AccessPolicy.ensure_candidate_owner(iv, current_user)
        if not settings.CANDIDATE_CAN_DOWNLOAD_RECORDINGS:
            raise HTTPException(403, "Candidates are not allowed to download recordings")
    else:
        AccessPolicy.ensure_interview_viewer(iv, current_user)

    if not iv.recording_url or not Path(iv.recording_url).exists():
        raise HTTPException(404, "Recording not found")

    p = Path(iv.recording_url)
    return _range_response(request, p, interview_token)


@router.delete("/{interview_token}", status_code=204)
async def delete_recording(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_interview(interview_token, db)
    if current_user.role not in (UserRole.ADMIN, UserRole.HR):
        raise HTTPException(403, "Access denied")
    AccessPolicy.ensure_hr_access(iv, current_user)

    if iv.recording_url:
        Path(iv.recording_url).unlink(missing_ok=True)
    iv.recording_url = None
    iv.recording_size_bytes = None
    await db.flush()
