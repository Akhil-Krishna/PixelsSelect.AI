"""
Global exception handlers — wrap every error in a consistent JSON envelope.
"""
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import get_request_id

logger = logging.getLogger(__name__)


def _envelope(code: str, message: str, detail: Any = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
            "detail": detail,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    if not settings.ENABLE_GLOBAL_ERROR_ENVELOPE:
        return

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException):
        logger.warning(
            "http exception",
            extra={
                "event": "http_exception",
                "component": "api",
                "endpoint": request.url.path,
                "request_id": get_request_id(),
                "error": str(exc.detail),
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail), detail=exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        logger.warning(
            "validation error",
            extra={
                "event": "validation_error",
                "component": "api",
                "endpoint": request.url.path,
                "request_id": get_request_id(),
                "error": str(exc.errors()),
            },
        )
        return JSONResponse(
            status_code=422,
            content=_envelope("validation_error", "Request validation failed", detail=exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception(
            "unhandled exception",
            extra={
                "event": "unhandled_exception",
                "component": "api",
                "endpoint": request.url.path,
                "request_id": get_request_id(),
                "error": str(exc),
            },
        )
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Internal server error"),
        )
