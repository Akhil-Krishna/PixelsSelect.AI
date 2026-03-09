"""
User and Organisation ORM models.
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    HR = "hr"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organisation(Base):
    """
    Tenant boundary.
    HR and Interviewers belong to one Organisation; Candidates may be external.
    """

    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Verification & plan
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan: Mapped[str] = mapped_column(String, default="free", nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    members: Mapped[List["User"]] = relationship("User", back_populates="organisation")

    def __repr__(self) -> str:
        return f"<Organisation id={self.id} name={self.name!r}>"


class User(Base):
    """Platform user — one of: admin | hr | interviewer | candidate."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.CANDIDATE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Verification & auth tracking
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auth_provider: Mapped[str] = mapped_column(String, default="local", nullable=False)
    invited_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    organisation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organisations.id"), nullable=True, index=True
    )
    organisation: Mapped[Optional["Organisation"]] = relationship(
        "Organisation", back_populates="members"
    )

    department_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    department: Mapped[Optional["Department"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Department", foreign_keys=[department_id]
    )

    # Relationships
    scheduled_interviews: Mapped[List["Interview"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Interview",
        foreign_keys="Interview.hr_id",
        back_populates="hr",
    )
    candidate_interviews: Mapped[List["Interview"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Interview",
        foreign_keys="Interview.candidate_id",
        back_populates="candidate",
    )
    interviewer_assignments: Mapped[List["InterviewInterviewer"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        "InterviewInterviewer", back_populates="interviewer"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
