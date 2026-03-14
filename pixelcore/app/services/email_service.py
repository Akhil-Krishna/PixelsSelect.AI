"""
Email service — multi-provider candidate/interviewer notifications.

Providers:
  log      — print-only, no actual send (dev default)
  sendgrid — SendGrid API
"""
import logging
from datetime import datetime, timezone
from typing import Optional
import html

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
            logger.info("[EMAIL LOG] to=%s subject=%s body=%s", to, subject, html_body)
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
        interview_title: str,
        scheduled_label: str,
    ) -> str:
        candidate_name = html.escape(candidate_name)
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <h2 style="color:#1f2937;">Interview Scheduled</h2>
          <p>Hello <strong>{candidate_name}</strong>,</p>
          <p>Your interview has been scheduled:</p>
          <table style="width:100%;border-collapse:collapse;margin:14px 0;background:#fff;border:1px solid #e5e7eb;border-radius:8px;">
            <tr><td style="padding:10px 12px;font-weight:600;color:#374151;width:36%;">Interview</td><td style="padding:10px 12px;">{interview_title}</td></tr>
            <tr style="background:#f3f4f6;"><td style="padding:10px 12px;font-weight:600;color:#374151;">Scheduled</td><td style="padding:10px 12px;">{scheduled_label}</td></tr>
          </table>
          <p style="background:#EFF6FF;border:1px solid #3B82F6;border-radius:8px;padding:14px;margin:16px 0;color:#1E40AF;font-size:14px;">
            \U0001f4e7 You will receive a <strong>separate email with your interview access link</strong> closer to the scheduled time. No login or registration is needed.
          </p>
        </div>
        """

    @staticmethod
    def _build_candidate_link_html(
        candidate_name: str,
        interview_title: str,
        scheduled_label: str,
        interview_link: str,
    ) -> str:
        candidate_name = html.escape(candidate_name)
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
                interview_title=interview_title,
                scheduled_label=label,
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


    def send_org_verification_email(
        self,
        admin_email: str,
        admin_name: str,
        org_name: str,
        verify_link: str,
    ) -> bool:
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:40px;">🤖</div>
            <h2 style="margin:8px 0;color:#1f2937;">Verify your organisation email</h2>
          </div>
          <p>Hello <strong>{admin_name}</strong>,</p>
          <p>You registered <strong>{org_name}</strong> on PixelsSelect.AI. Please verify your email to activate your account.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{verify_link}" style="background:#4F46E5;color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
              Verify Email Address
            </a>
          </div>
          <p style="font-size:12px;color:#6b7280;">This link expires in 24 hours. If you did not register, you can safely ignore this email.</p>
          <p style="font-size:12px;color:#9ca3af;">Direct link: {verify_link}</p>
        </div>
        """
        logger.info("[VERIFY LINK] %s", verify_link)
        return self.send_sync(
            to=admin_email,
            subject=f"Verify your email — {org_name} on PixelsSelect.AI",
            html_body=html,
        )

    def send_staff_invitation_email(
        self,
        to_email: str,
        org_name: str,
        invited_by_name: str,
        role: str,
        setup_link: str,
        expires_hours: int = 48,
    ) -> bool:
        role_label = role.replace("_", " ").title()
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:40px;">📧</div>
            <h2 style="margin:8px 0;color:#1f2937;">You’ve been invited</h2>
          </div>
          <p><strong>{invited_by_name}</strong> has invited you to join <strong>{org_name}</strong> as a <strong>{role_label}</strong> on PixelsSelect.AI.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{setup_link}" style="background:#4F46E5;color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
              Set Up Your Account
            </a>
          </div>
          <p style="font-size:12px;color:#6b7280;">This invitation expires in {expires_hours} hours. If you did not expect this invitation, you can ignore this email.</p>
          <p style="font-size:12px;color:#9ca3af;">Direct link: {setup_link}</p>
        </div>
        """
        logger.info("[INVITE LINK] %s", setup_link)
        return self.send_sync(
            to=to_email,
            subject=f"You’ve been invited to join {org_name} on PixelsSelect.AI",
            html_body=html,
        )

    def send_password_reset_email(
        self,
        to_email: str,
        full_name: str,
        reset_link: str,
    ) -> bool:
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:24px;border-radius:12px;">
          <div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:40px;">🔒</div>
            <h2 style="margin:8px 0;color:#1f2937;">Reset your password</h2>
          </div>
          <p>Hello <strong>{full_name}</strong>,</p>
          <p>We received a request to reset your PixelsSelect.AI password. Click the button below to set a new password.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{reset_link}" style="background:#DC2626;color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;">
              Reset Password
            </a>
          </div>
          <p style="font-size:12px;color:#6b7280;">This link expires in 1 hour. If you didn’t request a reset, you can safely ignore this email.</p>
          <p style="font-size:12px;color:#9ca3af;">Direct link: {reset_link}</p>
        </div>
        """
        logger.info("[RESET LINK] %s", reset_link)
        return self.send_sync(
            to=to_email,
            subject="Reset your PixelsSelect.AI password",
            html_body=html,
        )


# Singleton + module-level aliases
email_service = EmailService()
send_interview_invite_sync = email_service.send_interview_invite_sync
send_interview_link_sync = email_service.send_interview_link_sync
send_interviewer_notification_sync = email_service.send_interviewer_notification_sync
