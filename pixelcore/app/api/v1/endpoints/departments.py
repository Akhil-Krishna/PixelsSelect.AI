"""
Department CRUD and Question Bank management endpoints.
"""
import csv
import io
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_hr
from app.models.department import Department, DepartmentQuestionBank
from app.models.user import User
from app.schemas import DepartmentCreate, DepartmentOut, QuestionBankDetail, QuestionBankOut

router = APIRouter(prefix="/departments", tags=["departments"])
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dept_to_out(dept: Department) -> DepartmentOut:
    return DepartmentOut(
        id=dept.id,
        name=dept.name,
        organisation_id=dept.organisation_id,
        lead_id=dept.lead_id,
        lead_name=dept.lead.full_name if dept.lead else None,
        created_at=dept.created_at,
    )


def _parse_txt_questions(text: str) -> list[dict]:
    """Parse TXT file: one question per non-empty line.
    Lines starting with CODING: are marked as coding questions."""
    questions = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("CODING:"):
            questions.append({"question": line[7:].strip(), "type": "coding"})
        else:
            questions.append({"question": line, "type": "theory"})
    return questions


def _parse_csv_questions(text: str) -> list[dict]:
    """Parse CSV file with columns: question[, difficulty][, type].
    First row is treated as header if it contains 'question'."""
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    # Detect header
    header = [c.strip().lower() for c in rows[0]]
    has_header = "question" in header
    data_rows = rows[1:] if has_header else rows

    # Column indices
    q_idx = header.index("question") if has_header and "question" in header else 0
    d_idx = header.index("difficulty") if has_header and "difficulty" in header else None
    t_idx = header.index("type") if has_header and "type" in header else None

    questions = []
    for row in data_rows:
        if not row or not row[q_idx].strip():
            continue
        q: dict = {"question": row[q_idx].strip(), "type": "theory"}
        if d_idx is not None and d_idx < len(row) and row[d_idx].strip():
            q["difficulty"] = row[d_idx].strip()
        if t_idx is not None and t_idx < len(row) and row[t_idx].strip():
            q["type"] = row[t_idx].strip()
        questions.append(q)
    return questions


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a department within the admin's organisation."""
    if not current_user.organisation_id:
        raise HTTPException(400, "You must belong to an organisation to create a department.")

    # Unique name per org
    existing = await db.execute(
        select(Department).where(
            Department.organisation_id == current_user.organisation_id,
            Department.name == payload.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Department '{payload.name}' already exists in your organisation.")

    # Validate lead belongs to same org
    if payload.lead_id:
        lead = await db.execute(select(User).where(User.id == payload.lead_id))
        lead_user = lead.scalar_one_or_none()
        if not lead_user or lead_user.organisation_id != current_user.organisation_id:
            raise HTTPException(400, "Lead must belong to your organisation.")

    dept = Department(
        name=payload.name,
        organisation_id=current_user.organisation_id,
        lead_id=payload.lead_id,
    )
    db.add(dept)
    await db.flush()

    # Reload with relationships
    result = await db.execute(
        select(Department).options(selectinload(Department.lead)).where(Department.id == dept.id)
    )
    return _dept_to_out(result.scalar_one())


@router.get("", response_model=List[DepartmentOut])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """List departments in the caller's organisation."""
    if not current_user.organisation_id:
        return []
    result = await db.execute(
        select(Department)
        .options(selectinload(Department.lead))
        .where(Department.organisation_id == current_user.organisation_id)
        .order_by(Department.name)
    )
    return [_dept_to_out(d) for d in result.scalars().all()]


@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    result = await db.execute(
        select(Department).options(selectinload(Department.lead)).where(Department.id == department_id)
    )
    dept = result.scalar_one_or_none()
    if not dept or dept.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Department not found")
    return _dept_to_out(dept)


@router.delete("/{department_id}", status_code=204)
async def delete_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if not dept or dept.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Department not found")
    await db.delete(dept)


# ── Question Banks ────────────────────────────────────────────────────────────

@router.post("/{department_id}/question-banks", response_model=QuestionBankOut, status_code=201)
async def upload_question_bank(
    department_id: str,
    label: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Upload a question bank file (TXT or CSV) with a label."""
    # Validate department
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if not dept or dept.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Department not found")

    # Read and parse file
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded text (TXT or CSV).")

    fname = file.filename or "questions.txt"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "txt"

    if ext == "csv":
        questions = _parse_csv_questions(text)
    else:
        questions = _parse_txt_questions(text)

    if not questions:
        raise HTTPException(400, "No questions found in the uploaded file.")

    qb = DepartmentQuestionBank(
        department_id=department_id,
        label=label.strip(),
        file_name=fname,
        questions=questions,
    )
    db.add(qb)
    await db.flush()
    await db.refresh(qb)
    return qb


@router.get("/{department_id}/question-banks", response_model=List[QuestionBankOut])
async def list_question_banks(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """List question banks for a department."""
    # Validate department belongs to caller's org
    dept_result = await db.execute(select(Department).where(Department.id == department_id))
    dept = dept_result.scalar_one_or_none()
    if not dept or dept.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Department not found")

    result = await db.execute(
        select(DepartmentQuestionBank)
        .where(DepartmentQuestionBank.department_id == department_id)
        .order_by(DepartmentQuestionBank.label)
    )
    return result.scalars().all()


@router.get("/question-banks/{qb_id}", response_model=QuestionBankDetail)
async def get_question_bank_detail(
    qb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_hr),
):
    """Get a question bank with its parsed questions."""
    result = await db.execute(
        select(DepartmentQuestionBank)
        .options(selectinload(DepartmentQuestionBank.department))
        .where(DepartmentQuestionBank.id == qb_id)
    )
    qb = result.scalar_one_or_none()
    if not qb or qb.department.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Question bank not found")
    return qb


@router.delete("/question-banks/{qb_id}", status_code=204)
async def delete_question_bank(
    qb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(DepartmentQuestionBank)
        .options(selectinload(DepartmentQuestionBank.department))
        .where(DepartmentQuestionBank.id == qb_id)
    )
    qb = result.scalar_one_or_none()
    if not qb or qb.department.organisation_id != current_user.organisation_id:
        raise HTTPException(404, "Question bank not found")
    await db.delete(qb)
