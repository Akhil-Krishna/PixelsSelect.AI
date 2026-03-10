"""
Idempotency service — prevents duplicate mutations on retry.
"""
import hashlib
import json
import logging
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)


class IdempotencyService:
    """
    Request-level idempotency guard.

    Usage pattern (in endpoints):
        record, cached = await idempotency.check(db, scope, key, payload)
        if cached is not None:
            return MySchema.model_validate(cached)
        # ... do work ...
        await idempotency.store(db, record, result_dict)
    """

    @staticmethod
    def _hash(payload: dict) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    async def check(
        db: AsyncSession,
        scope: str,
        key: Optional[str],
        payload: dict,
    ) -> Tuple[Optional[IdempotencyKey], Optional[dict]]:
        """
        Returns (record, cached_response).
        If cached_response is not None, the caller should return it directly.
        """
        if not settings.ENABLE_IDEMPOTENCY or not key:
            return None, None

        request_hash = IdempotencyService._hash(payload)
        res = await db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        )
        existing = res.scalar_one_or_none()

        if not existing:
            record = IdempotencyKey(scope=scope, key=key, request_hash=request_hash)
            db.add(record)
            await db.flush()
            return record, None

        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key reused with different payload")

        if existing.response_json:
            return existing, json.loads(existing.response_json)

        return existing, None

    @staticmethod
    async def store(
        db: AsyncSession,
        record: Optional[IdempotencyKey],
        response: dict,
    ) -> None:
        if not settings.ENABLE_IDEMPOTENCY or record is None:
            return
        record.response_json = json.dumps(
            response, separators=(",", ":"), ensure_ascii=True
        )
        await db.flush()


idempotency_service = IdempotencyService()
check_idempotency = idempotency_service.check
store_idempotency_response = idempotency_service.store


async def cleanup_expired_keys(db: AsyncSession) -> int:
    """Delete idempotency rows past their expires_at (or older than 24h if null)."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete, or_

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    stmt = delete(IdempotencyKey).where(
        or_(
            IdempotencyKey.expires_at <= now,
            # Legacy rows without expires_at — use created_at fallback
            (IdempotencyKey.expires_at.is_(None)) & (IdempotencyKey.created_at <= cutoff),
        )
    )
    result = await db.execute(stmt)
    await db.flush()
    count = result.rowcount or 0
    if count:
        logger.info("Purged %d expired idempotency keys", count)
    return count

