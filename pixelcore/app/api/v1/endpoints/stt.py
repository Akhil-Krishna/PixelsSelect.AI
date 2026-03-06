"""
Speech-to-Text transcription endpoint.
"""
import base64

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.task_runner import run_task_with_fallback
from app.models.user import User
from app.services.whisper_service import transcribe_audio
from app.tasks.stt_tasks import transcribe_audio_task

router = APIRouter(prefix="/stt", tags=["stt"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(..., description="Audio blob — webm/ogg/wav"),
    language: str = Form(default="en"),
    _: User = Depends(get_current_user),
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        return {"text": "", "available": False, "provider": settings.STT_PROVIDER}

    if settings.STT_LOCAL_FASTPATH_ENABLED and not settings.CELERY_REALTIME_ENABLED:
        return await transcribe_audio(audio_bytes, language=language)

    async def fallback():
        return await transcribe_audio(audio_bytes, language=language)

    return await run_task_with_fallback(
        transcribe_audio_task,
        payload={
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
            "language": language,
        },
        fallback_callable=fallback,
        endpoint_name="/stt/transcribe",
        realtime=True,
    )
