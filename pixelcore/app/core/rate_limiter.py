"""
Rate-limiter singleton — shared across all endpoints.

Uses slowapi backed by in-memory storage.  Rates are relaxed in
development so local testing is never blocked.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

_IS_PROD = settings.APP_ENV == "production"

# Production: strict.  Dev/test: effectively unlimited.
AUTH_RATE = "5/minute" if _IS_PROD else "1000/minute"
FORGOT_RATE = "3/minute" if _IS_PROD else "1000/minute"
REGISTER_RATE = "3/minute" if _IS_PROD else "1000/minute"

limiter = Limiter(key_func=get_remote_address, default_limits=[])
