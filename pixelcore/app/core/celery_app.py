"""
Celery application factory.
Routes tasks to dedicated queues for AI, vision, STT, email, resume, and recording.
Only instantiated when CELERY_ENABLED=true.
"""
from celery import Celery

from app.core.config import settings


def _redis_url() -> str:
    return settings.REDIS_URL or "redis://localhost:6379/0"


celery_app = Celery(
    "pixelselect",
    broker=settings.CELERY_BROKER_URL or _redis_url(),
    backend=settings.CELERY_RESULT_BACKEND or _redis_url(),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=settings.CELERY_SOFT_TIME_LIMIT_SECONDS,
    task_time_limit=settings.CELERY_TIME_LIMIT_SECONDS,
    worker_max_tasks_per_child=200,
    result_expires=3600,
    timezone="UTC",
    task_default_queue="celery",
    task_routes={
        "app.tasks.ai_tasks.*": {"queue": "ai"},
        "app.tasks.vision_tasks.*": {"queue": "vision"},
        "app.tasks.stt_tasks.*": {"queue": "stt"},
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.resume_tasks.*": {"queue": "resume"},
        "app.tasks.recording_tasks.*": {"queue": "recording"},
    },
    broker_transport_options={
        "visibility_timeout": max(settings.CELERY_TIME_LIMIT_SECONDS * 3, 120),
        "socket_timeout": settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    },
    imports=(
        "app.tasks.ai_tasks",
        "app.tasks.vision_tasks",
        "app.tasks.stt_tasks",
        "app.tasks.email_tasks",
        "app.tasks.resume_tasks",
        "app.tasks.recording_tasks",
    ),
)

celery_app.autodiscover_tasks(["app.tasks"])
