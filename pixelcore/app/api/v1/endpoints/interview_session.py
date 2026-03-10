"""
Interview session — candidate chat, AI controls, live metrics, completion.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import SecurityService
from app.models.interview import (
    Interview, InterviewInterviewer, InterviewMessage, InterviewStatus, VisionLog,
)
from app.models.user import User, UserRole
from app.schemas import (
    CandidateVerifyRequest, ChatMessage, ChatResponse, CompleteInterviewRequest,
    EvaluationResult, InterviewWithInterviewers, InterviewerQuestion,
    MessageOut, ScoreBreakdown,
)
from app.services.access_policy import AccessPolicy
from app.services.interview_orchestrator import (
    chat_turn, complete_interview_evaluation, start_interview_ai,
)
from app.services.vision_service import aggregate_vision_logs

router = APIRouter(prefix="/interview-session", tags=["interview-session"])
logger = logging.getLogger(__name__)

_CANDIDATE_TOKEN_MINUTES = 120  # 2-hour session for candidate


async def _get_iv(token: str, db: AsyncSession) -> Interview:
    res = await db.execute(
        select(Interview)
        .options(
            selectinload(Interview.messages),
            selectinload(Interview.interviewers)
            .selectinload(InterviewInterviewer.interviewer)
            .selectinload(User.organisation),
            selectinload(Interview.candidate).selectinload(User.organisation),
            selectinload(Interview.hr).selectinload(User.organisation),
        )
        .where(Interview.access_token == token)
    )
    iv = res.scalar_one_or_none()
    if not iv:
        raise HTTPException(404, "Interview not found")
    return iv


# ── Candidate magic-link verification (public — no JWT required) ─────────────

@router.post("/verify-candidate/{interview_token}")
async def verify_candidate(
    interview_token: str,
    body: CandidateVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint for candidates arriving via magic link.
    Validates email + name, checks interview time window, issues JWT cookie.
    """
    iv = await _get_iv(interview_token, db)

    if iv.status == InterviewStatus.CANCELLED:
        raise HTTPException(400, "This interview has been cancelled.")
    if iv.status == InterviewStatus.COMPLETED:
        raise HTTPException(400, "This interview has already been completed.")

    # 1. Verify candidate identity — email must match (case-insensitive)
    candidate = iv.candidate
    if not candidate or candidate.email.lower() != body.email.strip().lower():
        raise HTTPException(403, "Email does not match the interview invitation.")

    # 2. Check time window (reuse same settings as AccessPolicy)
    now = datetime.now(timezone.utc)
    scheduled = iv.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    else:
        scheduled = scheduled.astimezone(timezone.utc)

    earliest = scheduled - timedelta(seconds=max(0, int(settings.INTERVIEW_JOIN_EARLY_SECONDS)))
    latest = scheduled + timedelta(seconds=max(0, int(settings.INTERVIEW_JOIN_LATE_SECONDS)))

    if now < earliest:
        early_mins = int(settings.INTERVIEW_JOIN_EARLY_SECONDS) // 60
        return JSONResponse(
            status_code=200,
            content={
                "status": "early",
                "message": f"Interview starts at {scheduled.isoformat()}. "
                           f"Please come back {early_mins} minutes before.",
                "scheduled_at": scheduled.isoformat(),
            },
        )
    if now > latest:
        return JSONResponse(
            status_code=200,
            content={"status": "expired", "message": "The interview window has closed."},
        )

    # 3. Update candidate info
    if body.name.strip() and body.name.strip() != candidate.full_name:
        candidate.full_name = body.name.strip()
    candidate.is_verified = True
    await db.flush()
    await db.commit()

    # 4. Issue JWT cookie
    token = SecurityService.create_access_token(
        data={"sub": candidate.id},
        expires_delta=timedelta(minutes=_CANDIDATE_TOKEN_MINUTES),
    )

    response = JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "message": "Verified. Redirecting to interview.",
            "interview_id": iv.id,
            "access_token": interview_token,
        },
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=_CANDIDATE_TOKEN_MINUTES * 60,
        path="/",
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return response


@router.get("/join/{interview_token}", response_model=InterviewWithInterviewers)
async def join_interview(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_interview_viewer(iv, current_user)
    if iv.status == InterviewStatus.SCHEDULED:
        AccessPolicy.ensure_candidate_join_window(iv, current_user)
    if iv.status == InterviewStatus.CANCELLED:
        raise HTTPException(400, "Interview cancelled")
    return iv  # type: ignore[return-value]


@router.post("/start/{interview_token}")
async def start_interview(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_candidate_owner(iv, current_user)
    if iv.status == InterviewStatus.SCHEDULED:
        AccessPolicy.ensure_candidate_join_window(iv, current_user)

    if iv.status == InterviewStatus.COMPLETED:
        raise HTTPException(400, "Interview already completed")

    if iv.status == InterviewStatus.IN_PROGRESS:
        msgs = sorted(iv.messages, key=lambda m: m.timestamp)
        return {
            "status": "resumed",
            "messages": [MessageOut.model_validate(m) for m in msgs],
            "ai_paused": iv.ai_paused,
        }

    iv.status = InterviewStatus.IN_PROGRESS
    iv.started_at = datetime.now(timezone.utc)
    await db.flush()

    ai_result = await start_interview_ai(iv)
    ai_msg = InterviewMessage(interview_id=iv.id, role="ai", content=ai_result.get("text", ""))
    db.add(ai_msg)
    await db.flush()
    await db.refresh(ai_msg)

    return {"status": "started", "messages": [MessageOut.model_validate(ai_msg)], "ai_paused": False}


@router.post("/chat/{interview_token}", response_model=List[MessageOut])
async def chat(
    interview_token: str,
    payload: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_candidate_owner(iv, current_user)

    if iv.status != InterviewStatus.IN_PROGRESS:
        raise HTTPException(400, "Interview not in progress")

    candidate_msg = InterviewMessage(
        interview_id=iv.id, role="candidate",
        content=payload.content, code_snippet=payload.code_snippet,
    )
    db.add(candidate_msg)
    await db.flush()
    await db.refresh(candidate_msg)

    if iv.ai_paused:
        return [MessageOut.model_validate(candidate_msg)]

    # B13: Reload messages to include the just-flushed candidate message
    await db.refresh(iv, ['messages'])
    msgs = sorted(iv.messages, key=lambda m: m.timestamp)
    ai_result = await chat_turn(iv, msgs, payload.content, payload.code_snippet)
    ai_text = ai_result.get("text", "")
    is_complete = bool(ai_result.get("is_complete"))

    ai_msg = InterviewMessage(interview_id=iv.id, role="ai", content=ai_text)
    db.add(ai_msg)
    await db.flush()
    await db.refresh(ai_msg)

    return [MessageOut.model_validate(candidate_msg), MessageOut.model_validate(ai_msg)]


@router.post("/end/{interview_token}")
async def end_interview_simple(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    No-body alias called by the candidate's frontend when the interview finishes.
    Delegates to the full evaluation pipeline with empty optional fields.
    """
    empty_payload = CompleteInterviewRequest()
    return await _run_complete(interview_token, empty_payload, db, current_user)


@router.post("/complete/{interview_token}", response_model=EvaluationResult)
async def complete_interview(
    interview_token: str,
    payload: CompleteInterviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _run_complete(interview_token, payload, db, current_user)


async def _run_complete(
    interview_token: str,
    payload: CompleteInterviewRequest,
    db: AsyncSession,
    current_user: User,
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_candidate_owner(iv, current_user)

    if iv.status == InterviewStatus.COMPLETED:
        return EvaluationResult(
            overall_score=float(iv.overall_score or 0),
            answer_score=float(iv.answer_score or 0),
            code_score=float(iv.code_score) if iv.code_score is not None else None,
            emotion_score=float(iv.emotion_score) if iv.emotion_score is not None else None,
            integrity_score=float(iv.integrity_score) if iv.integrity_score is not None else None,
            passed=bool(iv.passed),
            ai_feedback=iv.ai_feedback or "",
            cheating_score=float(iv.cheating_score) if iv.cheating_score is not None else None,
            cheating_flags=(iv.emotion_scores or {}).get("cheating_flags", []),
        )

    # B5: Only allow completing an IN_PROGRESS interview
    if iv.status != InterviewStatus.IN_PROGRESS:
        raise HTTPException(
            400,
            f"Cannot complete an interview with status '{iv.status.value}'. "
            "Interview must be in progress."
        )

    logs_res = await db.execute(
        select(VisionLog).where(VisionLog.interview_id == iv.id).order_by(VisionLog.timestamp)
    )
    vision_logs = logs_res.scalars().all()
    vision_summary: Optional[dict] = aggregate_vision_logs(vision_logs) if vision_logs else None
    if not vision_summary and payload.emotion_data:
        vision_summary = payload.emotion_data.model_dump()
    if vision_summary and payload.tab_switches:
        vision_summary["tab_switches"] = payload.tab_switches

    final_cheating: Optional[float] = None
    if vision_logs:
        final_cheating = round(float(max(l.cheating_score for l in vision_logs)), 1)
    elif payload.cheating_score is not None:
        final_cheating = float(payload.cheating_score)

    msgs = sorted(iv.messages, key=lambda m: m.timestamp)
    evaluation = await complete_interview_evaluation(iv, msgs, vision_summary, final_cheating)

    iv.status = InterviewStatus.COMPLETED
    iv.ended_at = datetime.now(timezone.utc)
    iv.answer_score = evaluation.get("answer_score")
    iv.code_score = evaluation.get("code_score")
    iv.emotion_score = evaluation.get("emotion_score")
    iv.integrity_score = evaluation.get("integrity_score")
    iv.cheating_score = evaluation.get("cheating_score")
    iv.overall_score = evaluation.get("overall_score")
    iv.passed = evaluation.get("passed")
    iv.ai_feedback = evaluation.get("ai_feedback")
    iv.emotion_scores = vision_summary
    await db.flush()

    score_bkd_data = {
        "answer_score": evaluation.get("answer_score", 0),
        "code_score": evaluation.get("code_score"),
        "emotion_score": evaluation.get("emotion_score"),
        "integrity_score": evaluation.get("integrity_score"),
        "overall_score": evaluation.get("overall_score", 0),
        "passed": evaluation.get("passed", False),
        "weights_used": evaluation.get("weights_used", {}),
    }

    return EvaluationResult(
        overall_score=evaluation.get("overall_score", 0),
        answer_score=evaluation.get("answer_score", 0),
        code_score=evaluation.get("code_score"),
        emotion_score=evaluation.get("emotion_score"),
        integrity_score=evaluation.get("integrity_score"),
        passed=bool(evaluation.get("passed")),
        strengths=evaluation.get("strengths", []),
        weaknesses=evaluation.get("weaknesses", []),
        ai_feedback=evaluation.get("ai_feedback", ""),
        cheating_score=evaluation.get("cheating_score"),
        score_breakdown=ScoreBreakdown(**score_bkd_data),
        cheating_flags=vision_summary.get("cheating_flags", []) if vision_summary else [],
    )


@router.get("/status/{interview_token}")
async def get_interview_status(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_interview_viewer(iv, current_user)
    return {
        "status": iv.status.value,
        "ai_paused": bool(iv.ai_paused),
        "started_at": iv.started_at,
    }


@router.get("/messages/{interview_token}", response_model=List[MessageOut])
async def get_messages(
    interview_token: str,
    since_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_interview_viewer(iv, current_user)
    msgs = sorted(iv.messages, key=lambda m: m.timestamp)
    if since_id:
        ids = [m.id for m in msgs]
        if since_id in ids:
            msgs = msgs[ids.index(since_id) + 1:]
    return [MessageOut.model_validate(m) for m in msgs]


@router.get("/metrics/{interview_token}")
async def get_live_metrics(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    AccessPolicy.ensure_interview_viewer(iv, current_user)

    recent_res = await db.execute(
        select(VisionLog)
        .where(VisionLog.interview_id == iv.id)
        .order_by(desc(VisionLog.timestamp))
        .limit(10)
    )
    recent = recent_res.scalars().all()

    if not recent:
        return {
            "frames_analyzed": 0, "status": iv.status.value, "ai_paused": iv.ai_paused,
            "confidence": None, "engagement": None, "stress": None,
            "cheating_score": 0.0, "cheating_flags": [], "tab_switches": 0,
            "look_away_count": 0, "multi_face_count": 0, "gaze_ok": True,
            "dominant_emotion": None, "face_count": None,
        }

    all_res = await db.execute(select(VisionLog).where(VisionLog.interview_id == iv.id))
    all_logs = all_res.scalars().all()
    latest = recent[0]

    def _avg(vals, default=None):
        return round(sum(vals) / len(vals), 1) if vals else default

    confs = [l.confidence_score for l in recent if l.confidence_score is not None]
    engs = [l.engagement_score for l in recent if l.engagement_score is not None]
    strs = [l.stress_score for l in recent if l.stress_score is not None]
    cheats = [l.cheating_score for l in recent if l.cheating_score is not None]

    def _flags_from_log(log: VisionLog) -> list[str]:
        if isinstance(log.cheating_flags, list):
            return [str(f) for f in log.cheating_flags]
        if isinstance(log.cheating_flags, dict):
            raw = log.cheating_flags.get("flags", [])
            return [str(f) for f in raw] if isinstance(raw, list) else []
        return []

    all_flags: list[str] = []
    look_away = 0
    multi_face = 0
    max_tab_switches = 0
    latest_flags = _flags_from_log(latest)

    for l in all_logs:
        flags = _flags_from_log(l)
        all_flags.extend(flags)
        max_tab_switches = max(max_tab_switches, int(l.tab_switch_count or 0))

        if (l.face_count or 1) > 1 or any(f.startswith("multiple_faces_") for f in flags):
            multi_face += 1
        if (l.face_count or 1) == 0 or "no_face_detected" in flags or "gaze_away" in flags:
            look_away += 1

    return {
        "frames_analyzed": len(all_logs),
        "confidence": _avg(confs),
        "engagement": _avg(engs),
        "stress": _avg(strs),
        "dominant_emotion": latest.dominant_emotion,
        "face_count": latest.face_count,
        "cheating_score": round(max(cheats), 1) if cheats else 0.0,
        "cheating_flags": list(set(all_flags))[-5:],
        "tab_switches": max_tab_switches,
        "look_away_count": look_away,
        "multi_face_count": multi_face,
        "gaze_ok": ((latest.face_count or 1) > 0) and ("gaze_away" not in latest_flags),
        "ai_paused": iv.ai_paused,
        "status": iv.status.value,
    }


@router.post("/pause-ai/{interview_token}")
async def pause_ai(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    if not AccessPolicy.is_org_viewer(iv, current_user):
        raise HTTPException(403, "Access denied")
    iv.ai_paused = True
    await db.flush()
    return {"ai_paused": True}


@router.post("/resume-ai/{interview_token}")
async def resume_ai(
    interview_token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    if not AccessPolicy.is_org_viewer(iv, current_user):
        raise HTTPException(403, "Access denied")
    iv.ai_paused = False
    await db.flush()
    return {"ai_paused": False}


@router.post("/ask/{interview_token}", response_model=MessageOut)
async def interviewer_ask(
    interview_token: str,
    payload: InterviewerQuestion,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iv = await _get_iv(interview_token, db)
    if not AccessPolicy.is_org_viewer(iv, current_user):
        raise HTTPException(403, "Access denied")
    if iv.status != InterviewStatus.IN_PROGRESS:
        raise HTTPException(400, "Interview not in progress")

    msg = InterviewMessage(
        interview_id=iv.id,
        role="interviewer",
        content=f"[Interviewer — {current_user.full_name}]: {payload.question}",
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return MessageOut.model_validate(msg)


# ── F6: Tab-switch reporting ──────────────────────────────────────────────────

class TabSwitchPayload(BaseModel):
    count: int = 0


@router.post("/tab-switch/{interview_token}")
async def report_tab_switch(
    interview_token: str,
    payload: TabSwitchPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist the candidate's tab-switch count directly to the interview."""
    result = await db.execute(
        select(Interview)
        .options(
            selectinload(Interview.interviewers)
            .selectinload(InterviewInterviewer.interviewer),
            selectinload(Interview.candidate),
        )
        .where(Interview.access_token == interview_token)
    )
    iv = result.scalar_one_or_none()
    if not iv:
        raise HTTPException(404, "Interview not found")
    AccessPolicy.ensure_candidate_owner(iv, current_user)

    # Only update if the new count is higher (monotonic)
    if payload.count > (iv.tab_switch_count or 0):
        iv.tab_switch_count = payload.count
        await db.flush()

    return {"tab_switch_count": iv.tab_switch_count}

