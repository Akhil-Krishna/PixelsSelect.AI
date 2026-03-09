"""
Invitation ORM model — staff invite-to-join flow.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import UserRole


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Invitation(Base):
    """
    Pending staff invitation sent by an admin.

    The raw token is emailed to the invitee; only the SHA-256 hash
    is stored here so the DB is useless even if leaked.
    """

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole", create_type=False), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    organisation: Mapped[Optional["Organisation"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Organisation", foreign_keys=[organisation_id]
    )
    inviter: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "User", foreign_keys=[invited_by]
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<Invitation id={self.id} email={self.email!r} role={self.role.value}>"
