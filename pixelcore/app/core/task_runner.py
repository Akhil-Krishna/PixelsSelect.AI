"""
Task dispatcher: run via Celery when available, fall back to direct async call.

Design:
  - run_task_with_fallback   — enqueue AND wait for result (realtime tasks)
  - enqueue_task_with_fallback — fire-and-forget (background tasks)

A circuit-breaker (_skip_until) prevents hammering a broken Celery/Redis by
adding a cooldown period after consecutive failures.
"""
import asyncio
import inspect
import logging
import time
from typing import Any, Awaitable, Callable, Optional

from celery.exceptions import TimeoutError as CeleryTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Circuit breaker ────────────────────────────────────────────────────────────
_skip_until: float = 0.0


async def _run_fallback(fn: Callable[[], Any] | Callable[[], Awaitable[Any]]) -> Any:
    if inspect.iscoroutinefunction(fn):
        return await fn()
    return await asyncio.to_thread(fn)


async def run_task_with_fallback(
    task_sig: Any,
    payload: dict,
    fallback_callable: Callable,
    wait_timeout: Optional[float] = None,
    endpoint_name: str = "",
    realtime: bool = False,
) -> Any:
    """
    Attempt to run *task_sig* via Celery and wait for its result.
    Falls back to *fallback_callable* when Celery is disabled, not configured
    for realtime tasks, or the broker is temporarily unreachable.
    """
    global _skip_until

    if not settings.CELERY_ENABLED:
        return await _run_fallback(fallback_callable)
    if realtime and not settings.CELERY_REALTIME_ENABLED:
        return await _run_fallback(fallback_callable)
    if not realtime and not settings.CELERY_BACKGROUND_ENABLED:
        return await _run_fallback(fallback_callable)
    if time.monotonic() < _skip_until:
        return await _run_fallback(fallback_callable)

    timeout = wait_timeout if wait_timeout is not None else settings.CELERY_WAIT_TIMEOUT_SECONDS
    enqueue_timeout = max(0.1, float(settings.CELERY_ENQUEUE_TIMEOUT_SECONDS))
    started = time.perf_counter()

    try:
        async_result = await asyncio.wait_for(
            asyncio.to_thread(task_sig.apply_async, kwargs={"payload": payload}),
            timeout=enqueue_timeout,
        )
        output = await asyncio.wait_for(
            asyncio.to_thread(async_result.get, timeout=timeout),
            timeout=max(timeout + 0.25, 0.5),
        )
        _skip_until = 0.0
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
        logger.info(
            "celery task completed",
            extra={
                "event": "task_complete",
                "component": "task_runner",
                "task_name": getattr(task_sig, "name", "unknown"),
                "endpoint": endpoint_name,
                "latency_ms": elapsed_ms,
            },
        )
        return output

    except (CeleryTimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
        _skip_until = time.monotonic() + settings.CELERY_FALLBACK_COOLDOWN_SECONDS
        logger.warning(
            "celery timeout; fallback",
            extra={
                "event": "task_timeout_fallback",
                "component": "task_runner",
                "task_name": getattr(task_sig, "name", "unknown"),
                "endpoint": endpoint_name,
                "error": str(exc),
            },
        )
        return await _run_fallback(fallback_callable)

    except Exception as exc:
        _skip_until = time.monotonic() + settings.CELERY_FALLBACK_COOLDOWN_SECONDS
        logger.warning(
            "celery error; fallback",
            extra={
                "event": "task_error_fallback",
                "component": "task_runner",
                "task_name": getattr(task_sig, "name", "unknown"),
                "endpoint": endpoint_name,
                "error": str(exc),
            },
        )
        return await _run_fallback(fallback_callable)


async def enqueue_task_with_fallback(
    task_sig: Any,
    payload: dict,
    fallback_callable: Callable,
    endpoint_name: str = "",
) -> Any:
    """
    Fire-and-forget: enqueue *task_sig* without waiting for a result.
    Immediately runs *fallback_callable* if enqueue fails.
    """
    global _skip_until

    if not settings.CELERY_ENABLED or not settings.CELERY_BACKGROUND_ENABLED:
        return await _run_fallback(fallback_callable)
    if time.monotonic() < _skip_until:
        return await _run_fallback(fallback_callable)

    enqueue_timeout = max(0.1, float(settings.CELERY_ENQUEUE_TIMEOUT_SECONDS))
    try:
        await asyncio.wait_for(
            asyncio.to_thread(task_sig.apply_async, kwargs={"payload": payload}),
            timeout=enqueue_timeout,
        )
        _skip_until = 0.0
        logger.info(
            "celery task enqueued",
            extra={
                "event": "task_enqueue",
                "component": "task_runner",
                "task_name": getattr(task_sig, "name", "unknown"),
                "endpoint": endpoint_name,
            },
        )
        return None
    except Exception as exc:
        _skip_until = time.monotonic() + settings.CELERY_FALLBACK_COOLDOWN_SECONDS
        logger.warning(
            "celery enqueue failed; fallback",
            extra={
                "event": "task_enqueue_fallback",
                "component": "task_runner",
                "task_name": getattr(task_sig, "name", "unknown"),
                "endpoint": endpoint_name,
                "error": str(exc),
            },
        )
        return await _run_fallback(fallback_callable)
