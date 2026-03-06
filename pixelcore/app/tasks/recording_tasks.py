"""Recording Celery tasks."""
from app.core.celery_app import celery_app
from app.services.recording_service import process_recording_metadata


@celery_app.task(
    name="app.tasks.recording_tasks.process_recording_metadata_task",
    bind=True,
    max_retries=2,
)
def process_recording_metadata_task(self, payload: dict) -> dict:
    try:
        return process_recording_metadata(
            payload["recording_path"], payload["size_bytes"]
        )
    except Exception as exc:
        raise self.retry(exc=exc)
