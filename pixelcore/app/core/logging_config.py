"""
Structured JSON logging + request-ID context variable.
"""
import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

# ── Request-ID context ─────────────────────────────────────────────────────────
_request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def set_request_id(rid: Optional[str]) -> None:
    _request_id_ctx.set(rid)


def get_request_id() -> Optional[str]:
    return _request_id_ctx.get()


def ensure_request_id(existing: Optional[str] = None) -> str:
    rid = (existing or "").strip() or str(uuid.uuid4())
    set_request_id(rid)
    return rid


# ── JSON log formatter ─────────────────────────────────────────────────────────
_EXTRA_KEYS = (
    "event", "component", "task_name", "endpoint",
    "request_id", "fallback", "latency_ms", "error",
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        payload.setdefault("request_id", get_request_id())
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
