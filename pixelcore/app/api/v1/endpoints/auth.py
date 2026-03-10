"""
Auth endpoints: login, logout, org registration, email verification,
forgot password, and reset password.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    generate_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.core.deps import get_current_user
from app.models.password_reset import PasswordResetToken
from app.models.user import Organisation, User, UserRole
from app.schemas import (
    CandidateRegisterRequest,
    EmailVerifyRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OrgOut,
    OrgRegisterOut,
    OrgRegisterRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserOut,
)
from app.services.email_service import email_service
from app.core.rate_limiter import limiter, AUTH_RATE, FORGOT_RATE, REGISTER_RATE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_MAX = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

# ── Shared helper ─────────────────────────────────────────────────────────────

def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=_COOKIE_MAX,
        path="/",
        samesite="lax",
        secure=not settings.DEBUG,
    )


# ── WebSocket token (for cross-origin WS auth) ──────────────────────────────

@router.get("/ws-token")
async def get_ws_token(
    current_user: User = Depends(get_current_user),
):
    """
    Return the raw JWT so the frontend can pass it as a WebSocket query param.
    WebSocket connections cannot send httpOnly cookies cross-origin, so this
    thin endpoint bridges that gap.  It is itself authenticated via the cookie.
    """
    token = create_access_token(data={"sub": current_user.id})
    return {"token": token}


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
@limiter.limit(AUTH_RATE)
async def login(
    request: Request, payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.organisation))
        .where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    # Staff must have verified their org email before they can log in
    if user.role in (UserRole.ADMIN, UserRole.HR, UserRole.INTERVIEWER) and not user.is_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Email not verified. Please check your inbox and verify your account first.",
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    await db.flush()   # persist last_login in this transaction

    token = create_access_token({"sub": user.id})
    _set_auth_cookie(response, token)
    return Token(access_token=token, user=UserOut.model_validate(user))  # type: ignore[arg-type]


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


# ── Candidate self-registration (candidates only) ─────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit(REGISTER_RATE)
async def register(request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Open self-registration for candidate accounts only."""
    if payload.role != UserRole.CANDIDATE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Self-registration is only allowed for candidate accounts. "
            "Staff accounts are created via invitation.",
        )
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=UserRole.CANDIDATE,
        is_verified=True,   # Candidates skip email verification
        auth_provider="local",
    )
    db.add(user)
    await db.flush()

    result = await db.execute(
        select(User).options(selectinload(User.organisation)).where(User.id == user.id)
    )
    return UserOut.model_validate(result.scalar_one())  # type: ignore[arg-type]


# ── Organisation registration ─────────────────────────────────────────────────

@router.post("/org/register", response_model=OrgRegisterOut, status_code=201)
async def org_register(
    payload: OrgRegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new organisation and create the first admin account.
    Sends a verification email; the org is inactive until verified.
    """
    # Check email not already taken
    existing_user = await db.execute(
        select(User).where(User.email == payload.admin_email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(400, "An account with this email already exists")

    # Check org name not already taken
    existing_org = await db.execute(
        select(Organisation).where(Organisation.name == payload.name)
    )
    if existing_org.scalar_one_or_none():
        raise HTTPException(400, "An organisation with this name already exists")

    # Infer domain from email if not supplied
    inferred_domain = payload.domain or payload.admin_email.split("@")[1].lower()

    org = Organisation(
        name=payload.name,
        domain=inferred_domain,
        is_verified=False,
        plan="free",
    )
    db.add(org)
    await db.flush()

    admin = User(
        email=payload.admin_email,
        full_name=payload.admin_name,
        hashed_password=get_password_hash(payload.password),
        role=UserRole.ADMIN,
        is_verified=False,
        auth_provider="local",
        organisation_id=org.id,
    )
    db.add(admin)
    await db.flush()

    # Generate verification token (stores hash in DB via a lightweight token record)
    raw_token, token_hash = generate_token()

    # We re-use PasswordResetToken as a generic "email verify" token keyed by user ID
    verify_record = PasswordResetToken(
        user_id=admin.id,
        token_hash=f"verify_{token_hash}",   # Prefix prevents cross-flow reuse
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    db.add(verify_record)
    await db.flush()

    verify_link = (
        f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    )

    background_tasks.add_task(
        email_service.send_org_verification_email,
        admin_email=admin.email,
        admin_name=admin.full_name,
        org_name=org.name,
        verify_link=verify_link,
    )

    logger.info("Org registered org_id=%s admin=%s", org.id, admin.email)

    # Re-load with relationships for response
    await db.refresh(admin)
    await db.refresh(org)

    result_user = await db.execute(
        select(User).options(selectinload(User.organisation)).where(User.id == admin.id)
    )
    admin_out = result_user.scalar_one()

    return OrgRegisterOut(
        organisation=OrgOut.model_validate(org),  # type: ignore[arg-type]
        user=UserOut.model_validate(admin_out),    # type: ignore[arg-type]
    )


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/org/verify-email")
async def verify_org_email(
    payload: EmailVerifyRequest, db: AsyncSession = Depends(get_db)
):
    """
    Verify an org admin's email using the raw token from the email link.
    Marks both the user and their organisation as verified.
    """
    token_hash = f"verify_{hash_token(payload.token)}"
    result = await db.execute(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used.is_(False),
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(400, "Invalid or already used verification link")
    if record.is_expired:
        raise HTTPException(400, "This verification link has expired. Please register again.")

    user = record.user
    if not user:
        raise HTTPException(400, "User not found")

    # Mark verified
    user.is_verified = True
    record.used = True

    # Also verify the org
    if user.organisation_id:
        org_res = await db.execute(
            select(Organisation).where(Organisation.id == user.organisation_id)
        )
        org = org_res.scalar_one_or_none()
        if org:
            org.is_verified = True

    await db.flush()
    logger.info("Email verified for user=%s org=%s", user.email, user.organisation_id)
    return {"message": "Email verified successfully. You can now log in."}


# ── Forgot password ───────────────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit(FORGOT_RATE)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a password reset email. Always returns 200 to prevent email enumeration.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        raw_token, token_hash = generate_token()
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.PASSWORD_RESET_EXPIRE_HOURS),
        )
        db.add(reset_record)
        await db.flush()

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

        background_tasks.add_task(
            email_service.send_password_reset_email,
            to_email=user.email,
            full_name=user.full_name,
            reset_link=reset_link,
        )
        logger.info("Password reset requested for user=%s", user.email)

    # Always return success to avoid email enumeration
    return {
        "message": "If that email is registered, you will receive a reset link shortly."
    }


# ── Reset password ────────────────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    """
    Consume a one-time password reset token and set the new password.
    Only plain password-reset tokens are accepted here — org-verify tokens
    have a 'verify_' prefix in their hash and will never match.
    """
    token_hash = hash_token(payload.token)

    # First: find the token regardless of used status for better diagnostics
    result = await db.execute(
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user))
        .where(PasswordResetToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(400, "Invalid or already used reset link")

    if record.used:
        raise HTTPException(400, "This reset link has already been used. Please request a new one.")

    if record.is_expired:
        raise HTTPException(400, "This reset link has expired. Please request a new one.")

    user = record.user
    if not user or not user.is_active:
        raise HTTPException(400, "User not found or disabled")

    user.hashed_password = get_password_hash(payload.new_password)
    record.used = True
    await db.flush()

    logger.info("Password reset completed for user=%s", user.email)
    return {"message": "Password reset successfully. You can now log in."}


# ── Optional candidate registration (post-interview) ─────────────────────────

@router.post("/candidate-register")
async def candidate_register(
    payload: CandidateRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Allows a candidate who joined via magic link to create a permanent
    account by setting a password.  Requires existing JWT (from verify-candidate).
    """
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(400, "Only candidates can use this endpoint.")
    if current_user.auth_provider != "magic_link":
        raise HTTPException(400, "Account already registered.")

    current_user.hashed_password = get_password_hash(payload.password)
    current_user.auth_provider = "local"
    current_user.is_verified = True
    await db.flush()

    # Re-issue a standard-length JWT and cookie
    token = create_access_token(data={"sub": current_user.id})
    _set_auth_cookie(response, token)

    logger.info("Candidate registered permanent account: %s", current_user.email)
    return {"message": "Account created. You can now log in with your email and password."}
