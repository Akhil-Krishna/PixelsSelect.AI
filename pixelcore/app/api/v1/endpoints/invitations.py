"""
Staff invitation endpoints — send, validate, and accept invitations.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import generate_token, get_password_hash, hash_token
from app.models.invitation import Invitation
from app.models.user import Organisation, User, UserRole
from app.schemas import InvitationAccept, InvitationCreate, InvitationOut, UserOut
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["invitations"])

_STAFF_ROLES = {UserRole.HR, UserRole.INTERVIEWER}


# ── Send invitation ───────────────────────────────────────────────────────────

@router.post("/send", status_code=201)
async def send_invitation(
    payload: InvitationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin sends a staff invitation.
    - Role must be HR or Interviewer (admin cannot be invited).
    - Invitee email domain must match the organisation domain.
    - If a pending (non-expired, non-accepted) invite already exists, it is
      invalidated and a fresh one is issued.
    """
    if payload.role not in _STAFF_ROLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You can only invite HR or Interviewer roles via invitation.",
        )

    if not current_user.organisation_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Your account is not linked to an organisation.",
        )

    # Domain check
    org_res = await db.execute(
        select(Organisation).where(Organisation.id == current_user.organisation_id)
    )
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(400, "Organisation not found")

    if org.domain:
        invite_domain = payload.email.split("@")[1].lower()
        if invite_domain != org.domain.lower():
            raise HTTPException(
                400,
                f"Invitation email must belong to your organisation domain (@{org.domain}). "
                f"Got @{invite_domain}.",
            )

    # Check if the user already exists
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(400, "A user with this email already exists.")

    # Invalidate any existing pending invitations for this email + org
    old_invites = await db.execute(
        select(Invitation).where(
            Invitation.email == payload.email,
            Invitation.organisation_id == org.id,
            Invitation.accepted.is_(False),
        )
    )
    for old in old_invites.scalars().all():
        # Mark it as expired by setting accepted=False and backdating expiry
        old.expires_at = datetime.now(timezone.utc)

    raw_token, token_hash = generate_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.INVITATION_EXPIRE_HOURS)

    invite = Invitation(
        organisation_id=org.id,
        email=payload.email,
        role=payload.role,
        token_hash=token_hash,
        invited_by=current_user.id,
        accepted=False,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()

    setup_link = f"{settings.FRONTEND_URL}/accept-invite?token={raw_token}"

    background_tasks.add_task(
        email_service.send_staff_invitation_email,
        to_email=payload.email,
        org_name=org.name,
        invited_by_name=current_user.full_name,
        role=payload.role.value,
        setup_link=setup_link,
        expires_hours=settings.INVITATION_EXPIRE_HOURS,
    )

    logger.info(
        "Invitation sent to=%s role=%s org=%s by=%s",
        payload.email, payload.role.value, org.name, current_user.email,
    )
    return {
        "message": f"Invitation sent to {payload.email}",
        "expires_at": expires_at.isoformat(),
    }


# ── Validate invitation token ─────────────────────────────────────────────────

@router.get("/validate/{token}", response_model=InvitationOut)
async def validate_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """
    Public endpoint — validate an invitation token and return invite details.
    Used by the frontend /accept-invite page to show org, role, and email to the invitee.
    """
    token_hash = hash_token(token)
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.organisation))
        .where(
            Invitation.token_hash == token_hash,
            Invitation.accepted.is_(False),
        )
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(404, "Invitation not found or already accepted.")
    if invite.is_expired:
        raise HTTPException(400, "This invitation has expired. Please ask your admin to resend it.")

    return InvitationOut(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        org_name=invite.organisation.name if invite.organisation else "",
        org_id=invite.organisation_id,
        expires_at=invite.expires_at,
        accepted=invite.accepted,
    )


# ── Accept invitation ─────────────────────────────────────────────────────────

@router.post("/accept", response_model=UserOut, status_code=201)
async def accept_invitation(
    payload: InvitationAccept, db: AsyncSession = Depends(get_db)
):
    """
    Staff member accepts their invitation by setting a full name and password.
    Creates their User account and marks the invitation as accepted.
    """
    token_hash = hash_token(payload.token)
    result = await db.execute(
        select(Invitation)
        .options(selectinload(Invitation.organisation))
        .where(
            Invitation.token_hash == token_hash,
            Invitation.accepted.is_(False),
        )
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(404, "Invitation not found or already accepted.")
    if invite.is_expired:
        raise HTTPException(400, "This invitation has expired. Please ask your admin to resend it.")

    # Guard against duplicate accounts (race condition)
    existing = await db.execute(select(User).where(User.email == invite.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "An account with this email already exists.")

    user = User(
        email=invite.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=invite.role,
        is_verified=True,          # Invitation implies email ownership verification
        is_active=True,
        auth_provider="local",
        organisation_id=invite.organisation_id,
        invited_by=invite.invited_by,
    )
    db.add(user)
    invite.accepted = True
    await db.flush()

    result2 = await db.execute(
        select(User).options(selectinload(User.organisation)).where(User.id == user.id)
    )
    created = result2.scalar_one()
    logger.info("Invitation accepted email=%s role=%s org=%s", user.email, user.role.value, invite.organisation_id)
    return UserOut.model_validate(created)  # type: ignore[arg-type]
