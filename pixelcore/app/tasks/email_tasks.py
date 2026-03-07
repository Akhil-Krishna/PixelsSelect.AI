"""Email Celery tasks."""
from app.core.celery_app import celery_app
from app.services.email_service import email_service


@celery_app.task(
    name="app.tasks.email_tasks.send_interview_invite_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_interview_invite_task(self, payload: dict) -> bool:
    try:
        return email_service.send_interview_invite_sync(**payload)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.email_tasks.send_interviewer_notification_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_interviewer_notification_task(self, payload: dict) -> bool:
    try:
        return email_service.send_interviewer_notification_sync(**payload)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.email_tasks.send_interview_link_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_interview_link_task(self, payload: dict) -> bool:
    try:
        return email_service.send_interview_link_sync(**payload)
    except Exception as exc:
        raise self.retry(exc=exc)
