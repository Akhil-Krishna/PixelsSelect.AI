"""
Pydantic request/response schemas.

Grouped by domain:
  auth | organisations | users | interviews | vision | chat | evaluation | recording
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.models.interview import InterviewStatus


# ─── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OrgRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    domain: Optional[str] = None            # e.g. "techcorp.com"
    admin_email: EmailStr
    admin_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)


class EmailVerifyRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class CandidateVerifyRequest(BaseModel):
    """Candidate identity verification before interview entry."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


class CandidateRegisterRequest(BaseModel):
    """Optional post-interview account creation."""
    password: str = Field(..., min_length=8)


# ─── Department ──────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    lead_id: Optional[str] = None


class DepartmentOut(BaseModel):
    id: str
    name: str
    organisation_id: str
    lead_id: Optional[str] = None
    lead_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionBankOut(BaseModel):
    id: str
    department_id: str
    label: str
    file_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionBankDetail(QuestionBankOut):
    questions: Optional[Any] = None


# ─── Organisation ──────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    domain: Optional[str] = None


class OrgOut(BaseModel):
    id: str
    name: str
    domain: Optional[str] = None
    is_verified: bool = False
    plan: str = "free"
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── User ─────────────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.CANDIDATE
    organisation_id: Optional[str] = None
    department_id: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime
    organisation_id: Optional[str] = None
    organisation: Optional[OrgOut] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


# Now that all dependent models are defined, define Token and OrgRegisterOut
# which reference both UserOut and OrgOut.
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class OrgRegisterOut(BaseModel):
    organisation: OrgOut
    user: UserOut
    message: str = "Verification email sent. Please check your inbox."


# ─── Invitation ──────────────────────────────────────────────────────────────────────

class InvitationCreate(BaseModel):
    email: EmailStr
    role: UserRole


class InvitationOut(BaseModel):
    id: str
    email: str
    role: UserRole
    org_name: str
    org_id: str
    expires_at: datetime
    accepted: bool

    model_config = {"from_attributes": True}


class InvitationAccept(BaseModel):
    token: str
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)


# ─── Interview ────────────────────────────────────────────────────────────────

class InterviewCreate(BaseModel):
    title: str
    job_role: str
    description: Optional[str] = None
    candidate_email: EmailStr
    interviewer_ids: List[str] = Field(default_factory=list)
    scheduled_at: datetime
    duration_minutes: int = 60
    enable_emotion_analysis: bool = True
    enable_cheating_detection: bool = True
    question_bank: Optional[List[dict]] = None
    department_id: Optional[str] = None
    question_bank_id: Optional[str] = None


class InterviewOut(BaseModel):
    id: str
    title: str
    job_role: str
    description: Optional[str] = None
    hr_id: str
    candidate_id: str
    organisation_id: Optional[str] = None
    department_id: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    status: InterviewStatus
    access_token: str
    enable_emotion_analysis: bool
    enable_cheating_detection: bool
    question_bank: Optional[Any] = None
    resume_path: Optional[str] = None
    ai_paused: bool = False
    answer_score: Optional[float] = None
    code_score: Optional[float] = None
    emotion_score: Optional[float] = None
    cheating_score: Optional[float] = None
    integrity_score: Optional[float] = None
    overall_score: Optional[float] = None
    passed: Optional[bool] = None
    ai_feedback: Optional[str] = None
    recording_url: Optional[str] = None
    recording_size_bytes: Optional[int] = None
    has_recording: bool = False
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    hr: Optional[UserOut] = None
    candidate: Optional[UserOut] = None

    model_config = {"from_attributes": True}


class InterviewerOut(BaseModel):
    id: str
    interviewer: UserOut

    model_config = {"from_attributes": True}


class InterviewWithInterviewers(InterviewOut):
    interviewers: List[InterviewerOut] = Field(default_factory=list)
    has_recording: bool = False

    model_config = {"from_attributes": True}


# ─── Vision ───────────────────────────────────────────────────────────────────

class FrameEmotionData(BaseModel):
    avg_confidence: float = 65.0
    avg_engagement: float = 65.0
    avg_stress: float = 20.0
    dominant_emotions: List[str] = Field(default_factory=list)
    cheating_flags: List[str] = Field(default_factory=list)
    frames_analyzed: int = 0
    max_cheating_score: float = 0.0
    avg_cheating_score: float = 0.0
    tab_switches: int = 0


# ─── Chat ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    content: str
    code_snippet: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    is_complete: bool = False
    ai_paused: bool = False


class CompleteInterviewRequest(BaseModel):
    cheating_score: Optional[float] = None
    emotion_data: Optional[FrameEmotionData] = None
    tab_switches: int = 0


# ─── Evaluation ───────────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    answer_score: float
    code_score: Optional[float] = None
    emotion_score: Optional[float] = None
    integrity_score: Optional[float] = None
    overall_score: float
    passed: bool
    weights_used: dict = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    overall_score: float
    answer_score: float
    code_score: Optional[float] = None
    emotion_score: Optional[float] = None
    integrity_score: Optional[float] = None
    passed: bool
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    ai_feedback: str
    cheating_score: Optional[float] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    cheating_flags: List[str] = Field(default_factory=list)


# ─── Message ──────────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    code_snippet: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# ─── Recording ────────────────────────────────────────────────────────────────

class RecordingUploadResponse(BaseModel):
    success: bool
    recording_url: str
    size_bytes: int
    message: str


# ─── Interviewer control ──────────────────────────────────────────────────────

class InterviewerQuestion(BaseModel):
    question: str


# ─── TTS ───────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str


# ── Forward-reference resolution ──────────────────────────────────────────────
Token.model_rebuild()
OrgOut.model_rebuild()
UserOut.model_rebuild()
InterviewOut.model_rebuild()
InterviewWithInterviewers.model_rebuild()
