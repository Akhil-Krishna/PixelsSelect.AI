"""STT Celery tasks."""
import asyncio
import base64
from app.core.celery_app import celery_app
from app.services.whisper_service import transcribe_audio


@celery_app.task(
    name="app.tasks.stt_tasks.transcribe_audio_task",
    bind=True,
    max_retries=2,
    default_retry_delay=1,
)
def transcribe_audio_task(self, payload: dict) -> dict:
    try:
        audio_bytes = base64.b64decode(payload["audio_b64"])
        language = payload.get("language", "en")
        return asyncio.run(transcribe_audio(audio_bytes, language))
    except Exception as exc:
        raise self.retry(exc=exc)
