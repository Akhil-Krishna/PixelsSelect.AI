"""
JWT creation/verification, bcrypt password hashing, and secure token utilities.
"""
import hashlib
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

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
        # Add unique JWT ID (JTI) for token blocklist support
        if "jti" not in payload:
            payload["jti"] = secrets.token_urlsafe(16)
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


# ── Secure single-use token utilities ─────────────────────────────────────────

def generate_token() -> Tuple[str, str]:
    """
    Return (raw_token, token_hash).

    raw_token  — sent in the email link, never stored.
    token_hash — SHA-256 hex digest stored in the database.
    """
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


def hash_token(raw: str) -> str:
    """SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Convenience singletons ─────────────────────────────────────────────────────
security = SecurityService()
verify_password = security.verify_password
get_password_hash = security.hash_password
create_access_token = security.create_access_token
decode_token = security.decode_token
