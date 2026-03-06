"""Resume Celery tasks."""
import asyncio
import base64
from app.core.celery_app import celery_app
from app.services.resume_service import extract_resume_text


@celery_app.task(
    name="app.tasks.resume_tasks.extract_resume_text_task",
    bind=True,
    max_retries=2,
)
def extract_resume_text_task(self, payload: dict) -> dict:
    try:
        content = base64.b64decode(payload["content_b64"])
        text = extract_resume_text(content, filename=payload.get("filename", "resume.pdf"))
        return {"text": text}
    except Exception as exc:
        raise self.retry(exc=exc)
