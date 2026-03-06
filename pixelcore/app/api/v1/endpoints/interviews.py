"""
Interview lifecycle endpoints — schedule, list, get, cancel, upload resume.
"""
import base64
import secrets
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_hr
from app.core.security import get_password_hash
from app.core.task_runner import enqueue_task_with_fallback, run_task_with_fallback
from app.models.interview import Interview, InterviewInterviewer, InterviewStatus
from app.models.user import User, UserRole
from app.schemas import InterviewCreate, InterviewWithInterviewers
from app.services.access_policy import AccessPolicy
from app.services.email_service import send_interview_invite_sync, send_interviewer_notification_sync
from app.services.idempotency_service import check_idempotency, store_idempotency_response
from app.services.resume_service import extract_resume_text
from app.tasks.email_tasks import send_interview_invite_task, send_interviewer_notification_task
from app.tasks.resume_tasks import extract_resume_text_task

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _eager_opts():
    return [
        selectinload(Interview.hr).selectinload(User.organisation),
        selectinload(Interview.candidate).selectinload(User.organisation),
        selectinload(Interview.interviewers)
        .selectinload(InterviewInterviewer.interviewer)
        .selectinload(User.organisation),
    ]


async def _load_interview(interview_id: str, db: AsyncSession) -> Interview:
    res = await db.execute(
        select(Interview).options(*_eager_opts()).where(Interview.id == interview_id)
    )
    iv = res.scalar_one_or_none()
    if not iv:
        raise HTTPException(404, "Interview not found")
    return iv


def _to_schema(iv: Interview, temp_password: Optional[str] = None) -> InterviewWithInterviewers:
    obj = InterviewWithInterviewers.model_validate(iv)  # type: ignore[arg-type]
    obj.has_recording = bool(iv.recording_url)
    obj.temp_password = temp_password
    return obj


@router.post("", response_model=InterviewWithInterviewers, status_code=201)
async def schedule_interview(
    payload: InterviewCreate,
    background_tasks: BackgroundTasks,
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    idem_payload = {
        "title": payload.title,
        "candidate_email": payload.candidate_email,
        "scheduled_at": payload.scheduled_at.isoformat(),
        "interviewer_ids": sorted(payload.interviewer_ids),
    }
    idem_record, cached = await check_idempotency(
        db, "interviews.schedule", x_idempotency_key, idem_payload
    )
    if cached:
        return InterviewWithInterviewers.model_validate(cached)

    # Candidate lookup / auto-create
    res = await db.execute(select(User).where(User.email == payload.candidate_email))
    candidate = res.scalar_one_or_none()
    temp_password = None

    if not candidate:
        temp_password = secrets.token_urlsafe(8)
        candidate = User(
            email=payload.candidate_email,
            full_name=payload.candidate_email.split("@")[0].replace(".", " ").title(),
            hashed_password=get_password_hash(temp_password),
            role=UserRole.CANDIDATE,
        )
        db.add(candidate)
        await db.flush()
    elif candidate.role != UserRole.CANDIDATE:
        raise HTTPException(400, "Candidate email belongs to a non-candidate account")

    interview = Interview(
        title=payload.title,
        job_role=payload.job_role,
        description=payload.description,
        hr_id=current_user.id,
        candidate_id=candidate.id,
        organisation_id=current_user.organisation_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        enable_emotion_analysis=payload.enable_emotion_analysis,
        enable_cheating_detection=payload.enable_cheating_detection,
        question_bank=payload.question_bank,
    )
    db.add(interview)
    await db.flush()

    hr_domain = current_user.email.split("@")[1].lower()
    for iid in payload.interviewer_ids:
        r = await db.execute(
            select(User)
            .options(selectinload(User.organisation))
            .where(User.id == iid, User.role == UserRole.INTERVIEWER)
        )
        interviewer = r.scalar_one_or_none()
        if not interviewer:
            continue
        if current_user.organisation_id and interviewer.organisation_id != current_user.organisation_id:
            raise HTTPException(400, f"Interviewer {interviewer.email} must belong to your organisation.")
        if interviewer.email.split("@")[1].lower() != hr_domain:
            raise HTTPException(400, f"Interviewer {interviewer.email} must share your email domain (@{hr_domain}).")

        db.add(InterviewInterviewer(interview_id=interview.id, interviewer_id=iid))

        notify_payload = {
            "interviewer_email": interviewer.email,
            "interviewer_name": interviewer.full_name,
            "interview_title": interview.title,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "dashboard_link": f"{settings.FRONTEND_URL}/",
        }
        background_tasks.add_task(
            enqueue_task_with_fallback,
            send_interviewer_notification_task,
            notify_payload,
            lambda p=notify_payload: send_interviewer_notification_sync(**p),
        )

    await db.flush()

    interview_link = f"{settings.FRONTEND_URL}/interview/{interview.access_token}"
    invite_payload = {
        "candidate_email": candidate.email,
        "candidate_name": candidate.full_name,
        "interview_title": interview.title,
        "scheduled_at": interview.scheduled_at.isoformat(),
        "interview_link": interview_link,
        "temp_password": temp_password,
    }
    background_tasks.add_task(
        enqueue_task_with_fallback,
        send_interview_invite_task,
        invite_payload,
        lambda p=invite_payload: send_interview_invite_sync(**p),
    )

    loaded = await _load_interview(interview.id, db)
    result_schema = _to_schema(loaded, temp_password)
    await store_idempotency_response(db, idem_record, result_schema.model_dump(mode="json"))  # type: ignore[arg-type]
    return result_schema


@router.get("", response_model=List[InterviewWithInterviewers])
async def list_interviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.ADMIN:
        query = select(Interview)
    elif current_user.role == UserRole.HR:
        query = (
            select(Interview)
            .join(Interview.hr)
            .where(User.organisation_id == current_user.organisation_id)
        )
    elif current_user.role == UserRole.CANDIDATE:
        query = select(Interview).where(Interview.candidate_id == current_user.id)
    elif current_user.role == UserRole.INTERVIEWER:
        subq = select(InterviewInterviewer.interview_id).where(
            InterviewInterviewer.interviewer_id == current_user.id
        )
        query = select(Interview).where(Interview.id.in_(subq))
    else:
        raise HTTPException(403, "Access denied")

    query = query.options(*_eager_opts()).order_by(Interview.scheduled_at.desc())
    result = await db.execute(query)
    return [_to_schema(iv) for iv in result.scalars().unique().all()]


@router.get("/{interview_id}", response_model=InterviewWithInterviewers)
async def get_interview(
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _load_interview(interview_id, db)
    AccessPolicy.ensure_interview_viewer(iv, current_user)
    return _to_schema(iv)


@router.delete("/{interview_id}", status_code=204)
async def cancel_interview(
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    iv = await _load_interview(interview_id, db)
    AccessPolicy.ensure_hr_access(iv, current_user)
    if iv.status == InterviewStatus.COMPLETED:
        raise HTTPException(400, "Cannot cancel a completed interview")
    iv.status = InterviewStatus.CANCELLED
    await db.flush()


@router.post("/{interview_id}/resume")
async def upload_resume(
    interview_id: str,
    file: UploadFile = File(...),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    iv = await _load_interview(interview_id, db)
    AccessPolicy.ensure_hr_access(iv, current_user)

    filename = file.filename or "resume.pdf"
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".txt"):
        raise HTTPException(400, "Unsupported file type. Use PDF or TXT.")

    content = await file.read()
    idem_record, cached = await check_idempotency(
        db, "interviews.resume", x_idempotency_key,
        {"interview_id": interview_id, "filename": filename, "size": len(content)},
    )
    if cached:
        return cached

    dest = Path(settings.UPLOADS_DIR) / "resumes" / f"{interview_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    extracted = await run_task_with_fallback(
        extract_resume_text_task,
        payload={"content_b64": base64.b64encode(content).decode("ascii"), "filename": filename},
        fallback_callable=lambda: {"text": extract_resume_text(content, filename=filename)},
        endpoint_name="/interviews/{id}/resume",
    )
    text = extracted.get("text", "")

    iv.resume_path = str(dest)
    iv.resume_text = text[:8000] if text else None
    await db.flush()

    response = {"success": True, "filename": filename, "has_text": bool(text)}
    await store_idempotency_response(db, idem_record, response)
    return response
