"""
Health-check endpoints — diagnostic status for all subsystems.
"""
import asyncio

from fastapi import APIRouter

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.redis_client import ping as redis_ping, queue_length

router = APIRouter(prefix="/health", tags=["health"])

_REQUIRED_TASKS = {
    "app.tasks.ai_tasks.generate_ai_response_task",
    "app.tasks.ai_tasks.generate_final_evaluation_task",
    "app.tasks.vision_tasks.analyze_vision_frame_task",
    "app.tasks.stt_tasks.transcribe_audio_task",
    "app.tasks.email_tasks.send_interview_invite_task",
    "app.tasks.email_tasks.send_interviewer_notification_task",
    "app.tasks.resume_tasks.extract_resume_text_task",
    "app.tasks.recording_tasks.process_recording_metadata_task",
}


@router.get("/celery")
async def celery_health():
    """Detailed Celery / Redis diagnostic probe."""
    from app.api.v1.endpoints.webrtc import room_manager

    redis_reachable = redis_ping()
    worker_reachable = False
    registered_tasks_ok = False
    worker_count_seen = 0

    if settings.CELERY_ENABLED:
        try:
            ping_result = await asyncio.to_thread(
                celery_app.control.ping, timeout=settings.REDIS_HEALTH_TIMEOUT_SECONDS
            )
            worker_reachable = bool(ping_result)
            worker_count_seen = len(ping_result or [])
            if worker_reachable:
                reg = await asyncio.to_thread(celery_app.control.inspect().registered)
                if reg:
                    seen: set = set()
                    for tasks in reg.values():
                        seen.update(tasks or [])
                    registered_tasks_ok = _REQUIRED_TASKS.issubset(seen)
        except Exception:
            worker_reachable = False

    q_len = queue_length("celery")
    degraded_reasons = []
    if not settings.CELERY_ENABLED:
        degraded_reasons.append("celery_disabled")
    if not redis_reachable:
        degraded_reasons.append("redis_unreachable")
    if settings.CELERY_ENABLED and not worker_reachable:
        degraded_reasons.append("worker_unreachable")
    if settings.CELERY_ENABLED and worker_reachable and not registered_tasks_ok:
        degraded_reasons.append("task_registration_mismatch")

    return {
        "celery_enabled": settings.CELERY_ENABLED,
        "celery_realtime_enabled": settings.CELERY_REALTIME_ENABLED,
        "celery_background_enabled": settings.CELERY_BACKGROUND_ENABLED,
        "realtime_mode": "celery" if settings.CELERY_REALTIME_ENABLED else "local",
        "redis_reachable": redis_reachable,
        "worker_reachable": worker_reachable,
        "queue_length": q_len,
        "registered_tasks_ok": registered_tasks_ok,
        "worker_count_seen": worker_count_seen,
        "room_backend": room_manager.backend_name(),
        "vision_persist_enabled": settings.VISION_PERSIST_ENABLED,
        "vision_persist_sampling_n": max(1, int(settings.VISION_LOG_SAMPLE_EVERY_N)),
        "degraded_reasons": degraded_reasons,
        "degraded": bool(degraded_reasons),
    }
