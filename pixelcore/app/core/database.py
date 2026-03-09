"""
Async PostgreSQL engine and session factory (SQLAlchemy 2 + asyncpg).
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

# ── Session factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base ───────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base."""


# ── Dependency: per-request DB session ────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[override]
    """
    FastAPI dependency that yields a transactional session.
    Commits on success, rolls back on any exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Table creation (DDL) ───────────────────────────────────────────────────────
async def init_db() -> None:
    """
    Create all tables that do not yet exist.
    In production prefer Alembic migrations; this is kept for convenience.
    """
    # Import models so their metadata is attached to Base before create_all.
    from app.models import user, interview, idempotency, invitation, password_reset, department  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
