"""
PasswordResetToken ORM model — forgot-password flow.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PasswordResetToken(Base):
    """
    Single-use password reset token tied to a user.

    Raw token is emailed; only the SHA-256 hash is persisted.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[user_id]
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<PasswordResetToken id={self.id} user_id={self.user_id}>"
