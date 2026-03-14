"""AI Celery tasks — offload LLM calls to dedicated 'ai' queue.

Uses thread pool executor to run async functions without creating
a new event loop for each task call.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.core.celery_app import celery_app
from app.services.ai_service import get_ai_response_from_payload, generate_final_evaluation_from_payload

# Shared thread pool for running async functions in sync Celery tasks
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-task-worker")


def _run_async(coro):
    """Run an async coroutine in a new event loop within a thread pool.
    
    This avoids the overhead of creating a new event loop for each task call.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.ai_tasks.generate_ai_response_task",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def generate_ai_response_task(self, payload: dict) -> dict:
    """Generate AI response for interview conversation.
    
    Runs the async AI service function in a thread pool to avoid
    blocking the Celery worker event loop.
    """
    try:
        return _run_async(get_ai_response_from_payload(payload))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.ai_tasks.generate_final_evaluation_task",
    bind=True,
    max_retries=2,
    default_retry_delay=3,
)
def generate_final_evaluation_task(self, payload: dict) -> dict:
    """Generate final evaluation for completed interview.
    
    Runs the async evaluation function in a thread pool to avoid
    blocking the Celery worker event loop.
    """
    try:
        return _run_async(generate_final_evaluation_from_payload(payload))
    except Exception as exc:
        raise self.retry(exc=exc)
