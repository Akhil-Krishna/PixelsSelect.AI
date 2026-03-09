"""
Public model registry — import this instead of individual model modules to
guarantee all metadata is attached to Base before create_all is called.
"""
from app.models.user import User, UserRole, Organisation  # noqa: F401
from app.models.department import Department, DepartmentQuestionBank  # noqa: F401
from app.models.interview import (  # noqa: F401
    Interview,
    InterviewInterviewer,
    InterviewMessage,
    InterviewStatus,
    VisionLog,
)
from app.models.idempotency import IdempotencyKey  # noqa: F401
from app.models.invitation import Invitation  # noqa: F401
from app.models.password_reset import PasswordResetToken  # noqa: F401
