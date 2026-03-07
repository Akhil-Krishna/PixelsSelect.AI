"""
Email service — multi-provider candidate/interviewer notifications.

Providers:
  log      — print-only, no actual send (dev default)
  sendgrid — SendGrid API
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_datetime(value: "datetime | str") -> datetime:
    if isinstance(value, datetime):
        return _as_utc(value)
    raw = str(value).strip().removesuffix(" UTC")
    try:
        return _as_utc(datetime.fromisoformat(raw))
    except ValueError:
        return _as_utc(datetime.strptime(raw, "%Y-%m-%d %H:%M"))


def _fmt_utc(dt: datetime) -> str:
    return _as_utc(dt).strftime("%Y-%m-%d %H:%M UTC")


class EmailService:
    """
    Thin email abstraction supporting log and SendGrid backends.
    All methods are synchronous inside; async wrappers are provided for
    FastAPI background tasks.
    """

    # ── Low-level send ─────────────────────────────────────────────────────────

    @staticmethod
    def send_sync(to: str, subject: str, html_body: str) -> bool:
        provider = settings.EMAIL_PROVIDER.strip().lower()

        if provider == "log":
            logger.info("[EMAIL LOG] to=%s subject=%s body=%.300s", to, subject, html_body)
            return True

        if provider == "sendgrid":
            api_key = settings.SENDGRID_API_KEY.strip()
            sender = (settings.SENDGRID_FROM_EMAIL or settings.EMAIL_FROM).strip()
            if not api_key or not sender:
                logger.error("SendGrid misconfigured: SENDGRID_API_KEY and SENDGRID_FROM_EMAIL required")
                return False
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                msg = Mail(from_email=sender, to_emails=to, subject=subject, html_content=html_body)
                resp = SendGridAPIClient(api_key).send(msg)
                ok = resp.status_code in (200, 202)
                if ok:
                    logger.info("SendGrid sent to=%s subject=%s", to, subject)
                else:
                    logger.error("SendGrid failed status=%s", resp.status_code)
                return ok
            except Exception as exc:
                logger.exception("SendGrid error: %s", exc)
                return False

        logger.warning("Unknown EMAIL_PROVIDER=%s", provider)
        return False

    # ── HTML builders ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_candidate_schedule_html(
        candidate_name: str,
        candidate_email: str,
        interview_title: str,
        scheduled_label: str,
        temp_password: Optional[str] = None,
    ) -> str:
        creds = ""
        if temp_password:
            creds = f"""
            <div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;padding:16px;margin:16px 0;">
              <p style="margin:0 0 8px;font-weight:700;color:#92400E;">Your Login Credentials</p>
              <p style="margin:4px 0;color:#78350F;">Email: <strong>{candidate_email}</strong></p>
              <p style="margin:4px 0;color:#78350F;">Password: <strong>{temp_password}</strong></p>
              <p style="margin:8px 0 0;font-size:12px;color:#92400E;">Log in before the interview starts.</p>
            </div>
            """
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <h2 style="color:#1f2937;">Interview Scheduled</h2>
          <p>Hello <strong>{candidate_name}</strong>,</p>
          <p>Your interview has been scheduled:</p>
          <table style="width:100%;border-collapse:collapse;margin:14px 0;background:#fff;border:1px solid #e5e7eb;border-radius:8px;">
            <tr><td style="padding:10px 12px;font-weight:600;color:#374151;width:36%;">Interview</td><td style="padding:10px 12px;">{interview_title}</td></tr>
            <tr style="background:#f3f4f6;"><td style="padding:10px 12px;font-weight:600;color:#374151;">Scheduled</td><td style="padding:10px 12px;">{scheduled_label}</td></tr>
          </table>
          {creds}
        </div>
        """

    @staticmethod
    def _build_candidate_link_html(
        candidate_name: str,
        interview_title: str,
        scheduled_label: str,
        interview_link: str,
    ) -> str:
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <h2 style="color:#1f2937;">Your Interview Link</h2>
          <p>Hello <strong>{candidate_name}</strong>, your interview is starting soon.</p>
          <table style="width:100%;border-collapse:collapse;margin:14px 0;background:#fff;border:1px solid #e5e7eb;border-radius:8px;">
            <tr><td style="padding:10px 12px;font-weight:600;color:#374151;width:36%;">Interview</td><td style="padding:10px 12px;">{interview_title}</td></tr>
            <tr style="background:#f3f4f6;"><td style="padding:10px 12px;font-weight:600;color:#374151;">Scheduled</td><td style="padding:10px 12px;">{scheduled_label}</td></tr>
          </table>
          <div style="text-align:center;margin:20px 0;">
            <a href="{interview_link}" style="background:#4F46E5;color:#fff;padding:12px 28px;text-decoration:none;border-radius:8px;font-weight:700;display:inline-block;">Join Interview</a>
          </div>
          <p style="font-size:12px;color:#6b7280;">Direct link: {interview_link}</p>
        </div>
        """

    # ── High-level send APIs ───────────────────────────────────────────────────

    def send_interview_invite_sync(
        self,
        candidate_email: str,
        candidate_name: str,
        interview_title: str,
        scheduled_at: "datetime | str",
        temp_password: Optional[str] = None,
    ) -> bool:
        """
        Immediate schedule notification (without join link).
        Reminder link delivery is scheduled separately via a task queue.
        """
        schedule_dt = _parse_datetime(scheduled_at)
        label = _fmt_utc(schedule_dt)

        return self.send_sync(
            to=candidate_email,
            subject=f"Interview Scheduled: {interview_title}",
            html_body=self._build_candidate_schedule_html(
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                interview_title=interview_title,
                scheduled_label=label,
                temp_password=temp_password,
            ),
        )

    def send_interview_link_sync(
        self,
        candidate_email: str,
        candidate_name: str,
        interview_title: str,
        scheduled_at: "datetime | str",
        interview_link: str,
    ) -> bool:
        schedule_dt = _parse_datetime(scheduled_at)
        label = _fmt_utc(schedule_dt)
        return self.send_sync(
            to=candidate_email,
            subject=f"Interview Link: {interview_title}",
            html_body=self._build_candidate_link_html(
                candidate_name=candidate_name,
                interview_title=interview_title,
                scheduled_label=label,
                interview_link=interview_link,
            ),
        )

    def send_interviewer_notification_sync(
        self,
        interviewer_email: str,
        interviewer_name: str,
        interview_title: str,
        scheduled_at: "datetime | str",
        dashboard_link: str,
    ) -> bool:
        label = _fmt_utc(_parse_datetime(scheduled_at))
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
          <h2>Interview Assignment</h2>
          <p>Hello <strong>{interviewer_name}</strong>,</p>
          <p>You have been assigned to: <strong>{interview_title}</strong></p>
          <p style="background:#f3f4f6;padding:10px 12px;border-radius:8px;"><strong>Scheduled:</strong> {label}</p>
          <div style="text-align:center;margin:18px 0;">
            <a href="{dashboard_link}" style="background:#4F46E5;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;">Open Dashboard</a>
          </div>
        </div>
        """
        return self.send_sync(
            to=interviewer_email,
            subject=f"Interview Assignment: {interview_title}",
            html_body=html,
        )


# Singleton + module-level aliases
email_service = EmailService()
send_interview_invite_sync = email_service.send_interview_invite_sync
send_interview_link_sync = email_service.send_interview_link_sync
send_interviewer_notification_sync = email_service.send_interviewer_notification_sync
