"""
Access-control policy rules shared by multiple endpoints.

Using a class with static methods groups all authz decisions
in one place, making it easy to audit and extend.
"""
import logging

from fastapi import HTTPException

from app.models.interview import Interview
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class AccessPolicy:
    """
    Centralised authorisation checks for interview access.

    All methods raise HTTP 403 on denial and return None on success,
    so callers can chain them without branching.
    """

    # ── Viewer access (HR / Interviewer / Admin) ───────────────────────────────

    @staticmethod
    def is_org_viewer(iv: Interview, user: User) -> bool:
        """
        True when *user* is authorised to watch/monitor *iv*.
        Enforces org-level isolation — HR can only view interviews in their own org.
        """
        if user.role == UserRole.ADMIN:
            return True
        if user.role == UserRole.HR:
            return (
                iv.hr is not None
                and iv.hr.organisation_id is not None
                and user.organisation_id == iv.hr.organisation_id
            )
        if user.role == UserRole.INTERVIEWER:
            return any(ii.interviewer_id == user.id for ii in iv.interviewers)
        return False

    @staticmethod
    def ensure_interview_viewer(iv: Interview, user: User) -> None:
        """Raise 403 unless *user* can view the interview (org viewer OR candidate)."""
        if AccessPolicy.is_org_viewer(iv, user):
            return
        if user.role == UserRole.CANDIDATE and iv.candidate_id == user.id:
            return
        logger.warning(
            "access denied: viewer",
            extra={
                "event": "policy_denied",
                "component": "authz",
                "error": f"user={user.id} interview={iv.id}",
            },
        )
        raise HTTPException(status_code=403, detail="Access denied")

    # ── Candidate ownership ────────────────────────────────────────────────────

    @staticmethod
    def ensure_candidate_owner(
        iv: Interview, user: User, message: str = "Access denied"
    ) -> None:
        """Raise 403 unless *user* is the candidate (or admin) for *iv*."""
        if user.role == UserRole.ADMIN or iv.candidate_id == user.id:
            return
        logger.warning(
            "access denied: candidate owner",
            extra={
                "event": "policy_denied",
                "component": "authz",
                "error": f"user={user.id} interview={iv.id}",
            },
        )
        raise HTTPException(status_code=403, detail=message)

    # ── HR / interview creator access ─────────────────────────────────────────

    @staticmethod
    def ensure_hr_access(iv: Interview, user: User) -> None:
        """Raise 403 unless *user* is admin or HR in the same org as *iv*."""
        if user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.HR:
            iv_org = iv.hr.organisation_id if iv.hr else None
            if iv_org and user.organisation_id == iv_org:
                return
        raise HTTPException(status_code=403, detail="Access denied")
