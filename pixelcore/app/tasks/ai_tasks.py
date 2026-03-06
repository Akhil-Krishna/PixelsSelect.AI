"""AI Celery tasks — offload LLM calls to dedicated 'ai' queue."""
import asyncio
from app.core.celery_app import celery_app
from app.services.ai_service import get_ai_response_from_payload, generate_final_evaluation_from_payload


@celery_app.task(
    name="app.tasks.ai_tasks.generate_ai_response_task",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def generate_ai_response_task(self, payload: dict) -> dict:
    try:
        return asyncio.run(get_ai_response_from_payload(payload))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.ai_tasks.generate_final_evaluation_task",
    bind=True,
    max_retries=2,
    default_retry_delay=3,
)
def generate_final_evaluation_task(self, payload: dict) -> dict:
    try:
        return asyncio.run(generate_final_evaluation_from_payload(payload))
    except Exception as exc:
        raise self.retry(exc=exc)
