"""
Department and DepartmentQuestionBank ORM models.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Department(Base):
    """Organisational department — groups users and question banks."""

    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey("organisations.id"), nullable=False, index=True
    )
    lead_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    organisation: Mapped["Organisation"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Organisation"
    )
    lead: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[lead_id]
    )
    question_banks: Mapped[List["DepartmentQuestionBank"]] = relationship(
        "DepartmentQuestionBank", back_populates="department", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name!r}>"


class DepartmentQuestionBank(Base):
    """Labeled question bank file belonging to a department."""

    __tablename__ = "department_question_banks"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    department_id: Mapped[str] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    questions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    department: Mapped["Department"] = relationship(
        "Department", back_populates="question_banks"
    )

    def __repr__(self) -> str:
        return f"<DepartmentQuestionBank id={self.id} label={self.label!r}>"
