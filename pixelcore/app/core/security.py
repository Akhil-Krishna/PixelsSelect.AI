"""
JWT creation/verification and bcrypt password hashing.
"""
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Suppress known bcrypt version detection noise
warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")
warnings.filterwarnings("ignore", ".*bcrypt.*")

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityService:
    """Stateless utilities for password hashing and JWT management."""

    @staticmethod
    def hash_password(plain: str) -> str:
        return _pwd_context.hash(plain)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)

    @staticmethod
    def create_access_token(
        data: dict,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        payload = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        payload["exp"] = expire
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except JWTError:
            return None


# ── Convenience singletons ─────────────────────────────────────────────────────
security = SecurityService()
verify_password = security.verify_password
get_password_hash = security.hash_password
create_access_token = security.create_access_token
decode_token = security.decode_token
