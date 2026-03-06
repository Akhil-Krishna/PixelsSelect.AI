"""
Vision frame analysis and summary endpoints.
"""
import asyncio
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.task_runner import run_task_with_fallback
from app.models.interview import Interview, VisionLog
from app.models.user import User
from app.services.access_policy import AccessPolicy
from app.services.vision_service import aggregate_vision_logs, analyze_frame
from app.tasks.vision_tasks import analyze_vision_frame_task

router = APIRouter(prefix="/vision", tags=["vision"])

_counters: Dict[str, int] = {}
_counter_lock = asyncio.Lock()


class FrameRequest(BaseModel):
    frame: str
    interview_id: Optional[str] = None
    tab_switch_count: int = 0
    frame_seq: Optional[int] = None


async def _should_persist(interview_id: str, frame_seq: Optional[int]) -> bool:
    if not settings.VISION_PERSIST_ENABLED:
        return False
    n = max(1, int(settings.VISION_LOG_SAMPLE_EVERY_N))
    if frame_seq is not None:
        return int(frame_seq) % n == 0
    async with _counter_lock:
        count = _counters.get(interview_id, 0) + 1
        _counters[interview_id] = count
    return count % n == 0


@router.post("/analyze")
async def analyze_vision_frame(
    payload: FrameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        async def fallback():
            return await analyze_frame(payload.frame)

        result = await run_task_with_fallback(
            analyze_vision_frame_task,
            payload={"frame": payload.frame},
            fallback_callable=fallback,
            endpoint_name="/vision/analyze",
            realtime=True,
        )
    except Exception as exc:
        return {
            "success": False, "error": str(exc),
            "confidence_score": 65.0, "engagement_score": 65.0,
            "stress_score": 20.0, "cheating_score": 0.0, "cheating_flags": [],
            "dominant_emotion": "neutral", "face_count": 1, "degraded": True,
        }

    if payload.interview_id and await _should_persist(payload.interview_id, payload.frame_seq):
        iv_res = await db.execute(select(Interview).where(Interview.id == payload.interview_id))
        iv = iv_res.scalar_one_or_none()
        if iv and iv.candidate_id == current_user.id:
            db.add(VisionLog(
                interview_id=iv.id,
                dominant_emotion=result.get("dominant_emotion"),
                confidence_score=result.get("confidence_score"),
                engagement_score=result.get("engagement_score"),
                stress_score=result.get("stress_score"),
                emotions_raw=result.get("emotions"),
                face_count=result.get("face_count", 1),
                gaze_deviation=result.get("gaze_deviation"),
                cheating_flags=result.get("cheating_flags"),
                cheating_score=result.get("cheating_score", 0.0),
                tab_switch_count=payload.tab_switch_count,
            ))
            await db.flush()

    return result


@router.get("/summary/{interview_id}")
async def get_vision_summary(
    interview_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv_res = await db.execute(select(Interview).where(Interview.id == interview_id))
    iv = iv_res.scalar_one_or_none()
    if not iv:
        raise HTTPException(404, "Interview not found")
    AccessPolicy.ensure_interview_viewer(iv, current_user)

    res = await db.execute(
        select(VisionLog)
        .where(VisionLog.interview_id == interview_id)
        .order_by(VisionLog.timestamp)
    )
    logs = res.scalars().all()
    return aggregate_vision_logs(logs) if logs else {"frames_analyzed": 0}
