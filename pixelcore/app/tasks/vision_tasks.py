"""Vision Celery tasks."""
import asyncio
from app.core.celery_app import celery_app
from app.services.vision_service import analyze_frame


@celery_app.task(
    name="app.tasks.vision_tasks.analyze_vision_frame_task",
    bind=True,
    max_retries=1,
    default_retry_delay=1,
)
def analyze_vision_frame_task(self, payload: dict) -> dict:
    try:
        return asyncio.run(analyze_frame(payload["frame"]))
    except Exception as exc:
        raise self.retry(exc=exc)
