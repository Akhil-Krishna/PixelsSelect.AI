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
from app.models.user import Organisation, User, UserRole
from app.schemas import OrgCreate, OrgOut, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
org_router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/interviewers", response_model=List[UserOut])
async def list_interviewers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """List active interviewers. HR sees only their own org."""
    query = (
        select(User)
        .options(selectinload(User.organisation))
        .where(User.role == UserRole.INTERVIEWER, User.is_active.is_(True))
    )
    if current_user.role == UserRole.HR and current_user.organisation_id:
        query = query.where(User.organisation_id == current_user.organisation_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("", response_model=List[UserOut])
async def list_users(
    role: Optional[UserRole] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User).options(selectinload(User.organisation))
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        organisation_id=payload.organisation_id or current_user.organisation_id,
    )
    db.add(user)
    await db.flush()

    result = await db.execute(
        select(User).options(selectinload(User.organisation)).where(User.id == user.id)
    )
    return result.scalar_one()


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await db.flush()
    await db.refresh(user)
    return user


# ── Organisations ─────────────────────────────────────────────────────────────

@org_router.get("", response_model=List[OrgOut])
async def list_orgs(db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    result = await db.execute(select(Organisation))
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
