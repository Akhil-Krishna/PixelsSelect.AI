"""
FastAPI dependency: resolve and authorise the current authenticated user.
"""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    auth_cookie: Optional[str] = Cookie(default=None, alias="access_token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the JWT from Bearer header or httpOnly cookie."""
    token: Optional[str] = None
    if credentials:
        token = credentials.credentials
    elif auth_cookie:
        token = auth_cookie

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    # Eagerly load organisation — lazy-loading breaks inside async serialisation
    result = await db.execute(
        select(User)
        .options(selectinload(User.organisation))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or disabled")

    return user


# ── Role guard factory ─────────────────────────────────────────────────────────

def require_roles(*roles: UserRole):
    """Return a dependency that enforces at least one of *roles*."""
    async def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _guard


# ── Convenience shorthands ─────────────────────────────────────────────────────
require_admin = require_roles(UserRole.ADMIN)
require_hr = require_roles(UserRole.ADMIN, UserRole.HR)
require_interviewer = require_roles(UserRole.ADMIN, UserRole.HR, UserRole.INTERVIEWER)
