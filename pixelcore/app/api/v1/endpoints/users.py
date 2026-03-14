"""
Users and Organisations endpoints.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_hr
from app.core.security import get_password_hash
from app.models.department import Department
from app.models.user import Organisation, User, UserRole
from app.schemas import OrgCreate, OrgOut, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
org_router = APIRouter(prefix="/organisations", tags=["organisations"])


def _enrich_user(user: User) -> dict:
    """Add computed fields (e.g. department_name) to UserOut response."""
    data = UserOut.model_validate(user).model_dump()
    data["department_name"] = user.department.name if user.department else None
    return data


@router.get("/me", response_model=UserOut)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Reload with department relationship
    from sqlalchemy.orm import selectinload as _sil
    result = await db.execute(
        select(User)
        .options(_sil(User.organisation), _sil(User.department))
        .where(User.id == current_user.id)
    )
    return _enrich_user(result.scalar_one())


@router.get("/me/stats")
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return role-specific interview analytics for the current user."""
    from sqlalchemy import func
    from app.models.interview import Interview, InterviewInterviewer, InterviewStatus

    role = current_user.role

    if role == UserRole.ADMIN:
        # Admin: ALL interviews across the entire organisation
        org_filter = (
            Interview.organisation_id == current_user.organisation_id
            if current_user.organisation_id
            else True  # superadmin fallback — see all
        )
        base = select(func.count()).select_from(Interview).where(org_filter)
    elif role == UserRole.HR:
        # HR: interviews they scheduled
        base = select(func.count()).select_from(Interview).where(
            Interview.hr_id == current_user.id
        )
    elif role == UserRole.INTERVIEWER:
        # Interviewer: interviews they were assigned to
        base = (
            select(func.count())
            .select_from(Interview)
            .join(InterviewInterviewer, Interview.id == InterviewInterviewer.interview_id)
            .where(InterviewInterviewer.interviewer_id == current_user.id)
        )
    else:
        # Candidate: interviews they participated in
        base = select(func.count()).select_from(Interview).where(
            Interview.candidate_id == current_user.id
        )

    total_r = await db.execute(base)
    total = total_r.scalar() or 0

    completed_r = await db.execute(base.where(Interview.status == InterviewStatus.COMPLETED))
    completed = completed_r.scalar() or 0

    passed_r = await db.execute(base.where(Interview.passed.is_(True)))
    passed = passed_r.scalar() or 0

    failed_r = await db.execute(base.where(Interview.passed.is_(False)))
    failed = failed_r.scalar() or 0

    pass_rate = round((passed / completed) * 100, 1) if completed > 0 else 0.0

    result = {
        "total": total,
        "completed": completed,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "role": role.value,
    }

    # Admin gets extra org-wide metrics
    if role == UserRole.ADMIN:
        org_filter_clause = (
            Interview.organisation_id == current_user.organisation_id
            if current_user.organisation_id
            else True
        )
        scheduled_r = await db.execute(
            select(func.count()).select_from(Interview)
            .where(org_filter_clause, Interview.status == InterviewStatus.SCHEDULED)
        )
        in_progress_r = await db.execute(
            select(func.count()).select_from(Interview)
            .where(org_filter_clause, Interview.status == InterviewStatus.IN_PROGRESS)
        )
        cancelled_r = await db.execute(
            select(func.count()).select_from(Interview)
            .where(org_filter_clause, Interview.status == InterviewStatus.CANCELLED)
        )
        avg_r = await db.execute(
            select(func.avg(Interview.overall_score)).select_from(Interview)
            .where(org_filter_clause, Interview.overall_score.isnot(None))
        )
        # Count distinct interviewers and candidates in org
        interviewers_r = await db.execute(
            select(func.count(func.distinct(User.id)))
            .where(User.organisation_id == current_user.organisation_id,
                   User.role == UserRole.INTERVIEWER, User.is_active.is_(True))
        )
        candidates_r = await db.execute(
            select(func.count(func.distinct(Interview.candidate_id)))
            .select_from(Interview)
            .where(org_filter_clause)
        )

        avg_score = avg_r.scalar()
        result.update({
            "scheduled": scheduled_r.scalar() or 0,
            "in_progress": in_progress_r.scalar() or 0,
            "cancelled": cancelled_r.scalar() or 0,
            "avg_score": round(float(avg_score), 1) if avg_score else 0.0,
            "total_interviewers": interviewers_r.scalar() or 0,
            "total_candidates": candidates_r.scalar() or 0,
        })

    return result


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-edit: users can update their own full_name only."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    await db.flush()
    result = await db.execute(
        select(User)
        .options(selectinload(User.organisation), selectinload(User.department))
        .where(User.id == current_user.id)
    )
    return _enrich_user(result.scalar_one())


@router.get("/interviewers", response_model=List[UserOut])
async def list_interviewers(
    department_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """List active interviewers scoped to the caller's organisation and optionally a department."""
    query = (
        select(User)
        .options(selectinload(User.organisation), selectinload(User.department))
        .where(User.role == UserRole.INTERVIEWER, User.is_active.is_(True))
    )
    if current_user.organisation_id:
        query = query.where(User.organisation_id == current_user.organisation_id)
    if department_id:
        query = query.where(User.department_id == department_id)
    result = await db.execute(query)
    users = result.scalars().all()
    return [_enrich_user(u) for u in users]


@router.get("", response_model=List[UserOut])
async def list_users(
    role: Optional[UserRole] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List users scoped to the admin's own organisation."""
    query = select(User).options(selectinload(User.organisation), selectinload(User.department))
    if current_user.organisation_id:
        query = query.where(User.organisation_id == current_user.organisation_id)
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query)
    return [_enrich_user(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Prevent adding another admin via this endpoint — use org/register for that.
    if payload.role == UserRole.ADMIN:
        raise HTTPException(400, "Admin accounts are created via organisation registration, not this endpoint.")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        organisation_id=payload.organisation_id or current_user.organisation_id,
        department_id=payload.department_id,
        is_verified=True,
        auth_provider="local",
    )
    # Validate department belongs to org
    if user.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == user.department_id))
        dept = dept_result.scalar_one_or_none()
        if not dept or dept.organisation_id != (user.organisation_id or current_user.organisation_id):
            raise HTTPException(400, "Department does not belong to this organisation.")
    db.add(user)
    await db.flush()

    result = await db.execute(
        select(User).options(selectinload(User.organisation), selectinload(User.department)).where(User.id == user.id)
    )
    return _enrich_user(result.scalar_one())


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    # Prevent cross-org tampering
    if current_user.organisation_id and user.organisation_id != current_user.organisation_id:
        raise HTTPException(403, "You can only manage users within your own organisation.")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await db.flush()
    # Reload with relationships to avoid MissingGreenlet (B4)
    result = await db.execute(
        select(User)
        .options(selectinload(User.organisation), selectinload(User.department))
        .where(User.id == user_id)
    )
    return _enrich_user(result.scalar_one())


# ── Organisations ─────────────────────────────────────────────────────────────

@org_router.get("", response_model=List[OrgOut])
async def list_orgs(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    query = select(Organisation)
    if current_user.organisation_id:
        query = query.where(Organisation.id == current_user.organisation_id)
    result = await db.execute(query)
    return result.scalars().all()


@org_router.post("", response_model=OrgOut, status_code=201)
async def create_org(
    payload: OrgCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(select(Organisation).where(Organisation.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Organisation already exists")
    org = Organisation(name=payload.name, domain=payload.domain)
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org
