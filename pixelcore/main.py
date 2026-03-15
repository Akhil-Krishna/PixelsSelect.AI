"""
PixelSelect AI Interview Platform — FastAPI application entry point.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.error_handlers import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

# ── Logging must be configured before anything else emits a log ───────────────
try:
    setup_logging(level=logging.DEBUG if settings.DEBUG else logging.INFO)
except Exception:
    logging.basicConfig(level=logging.INFO)


# ── Demo seed data ─────────────────────────────────────────────────────────────
async def _seed_demo_data() -> None:
    from app.core.security import get_password_hash
    from app.models.user import Organisation, User, UserRole

    async with AsyncSessionLocal() as session:
        # B3/B11: Never seed demo data in production
        if settings.APP_ENV == "production":
            logging.getLogger(__name__).warning(
                "SEED_DEMO_DATA is true but APP_ENV=production — skipping seed"
            )
            return

        existing = await session.execute(
            select(User).where(User.email == "admin@demo.com")
        )
        if existing.scalar_one_or_none():
            return

        org = Organisation(name="Demo Corp", domain="demo.com")
        session.add(org)
        await session.flush()

        demo_users = [
            User(email="admin@demo.com",       full_name="Admin User",       role=UserRole.ADMIN,
                 hashed_password=get_password_hash("admin123"), organisation_id=org.id,
                 is_verified=True),
            User(email="hr@demo.com",           full_name="HR Manager",       role=UserRole.HR,
                 hashed_password=get_password_hash("hr123456"), organisation_id=org.id,
                 is_verified=True),
            User(email="interviewer@demo.com",  full_name="Tech Interviewer", role=UserRole.INTERVIEWER,
                 hashed_password=get_password_hash("int12345"), organisation_id=org.id,
                 is_verified=True),
            User(email="candidate@demo.com",    full_name="John Candidate",   role=UserRole.CANDIDATE,
                 hashed_password=get_password_hash("can12345"),
                 is_verified=True),
        ]
        session.add_all(demo_users)
        await session.commit()
        print("✅ Demo data seeded  [admin@demo.com / admin123  |  hr@demo.com / hr123456  |  candidate@demo.com / can12345]")


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload/recording directories exist
    Path(settings.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOADS_DIR, "resumes").mkdir(parents=True, exist_ok=True)
    Path("recordings").mkdir(parents=True, exist_ok=True)

    # Create DB tables (idempotent — safe in all environments)
    await init_db()

    # Seed demo users in DEBUG mode
    if settings.DEBUG and settings.SEED_DEMO_DATA:
        await _seed_demo_data()

    # Background model warmups — server is ready immediately, warmup continues asynchronously
    try:
        from app.services.whisper_service import warmup_model
        asyncio.create_task(warmup_model())
    except Exception as e:
        logging.getLogger(__name__).warning("Whisper warmup skipped: %s", e)

    if settings.ENABLE_VISION_WARMUP:
        try:
            from app.services.vision_service import warmup_vision
            asyncio.create_task(warmup_vision())
        except Exception as e:
            logging.getLogger(__name__).warning("Vision warmup skipped: %s", e)

    if settings.ENABLE_TTS_WARMUP:
        try:
            from app.services.tts_service import warmup_tts
            asyncio.create_task(warmup_tts())
        except Exception as e:
            logging.getLogger(__name__).warning("TTS warmup skipped: %s", e)

    # Startup banner
    print("=" * 62)
    print(f"  {settings.APP_NAME:<30}  env={settings.APP_ENV}")
    print(f"  LLM_PROVIDER    : {settings.LLM_PROVIDER}")
    print(f"  VISION_PROVIDER : {settings.VISION_PROVIDER}")
    stt_model = settings.GROQ_STT_MODEL if settings.STT_PROVIDER == "groq" else settings.STT_MODEL
    print(f"  STT_PROVIDER    : {settings.STT_PROVIDER}  ({stt_model})")
    print(f"  TTS_PROVIDER    : {settings.TTS_PROVIDER}")
    print(f"  EMAIL_PROVIDER  : {settings.EMAIL_PROVIDER}")
    print(f"  CELERY_ENABLED  : {settings.CELERY_ENABLED}")
    print(f"  DB              : {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print("=" * 62)

    # B20: Periodic idempotency key cleanup (every hour)
    async def _idempotency_cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # 1 hour
            try:
                async with AsyncSessionLocal() as session:
                    from app.services.idempotency_service import cleanup_expired_keys
                    await cleanup_expired_keys(session)
                    await session.commit()
            except Exception as e:
                logging.getLogger(__name__).warning("Idempotency cleanup error: %s", e)

    cleanup_task = asyncio.create_task(_idempotency_cleanup_loop())

    yield

    # Cancel cleanup on shutdown
    cleanup_task.cancel()

    try:
        import app.core.async_redis_client as _arc
        if _arc._client:
            await _arc._client.aclose()
        if _arc._pool:
            await _arc._pool.aclose()
    except Exception as e:
        logging.getLogger(__name__).debug("Redis pool close error: %s", e)


# ── Application factory ────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="AI-Powered Interview Platform — PixelSelect",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
_cors_origins = ["*"] if settings.DEBUG else [settings.FRONTEND_URL]
_cors_credentials = not ("*" in _cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request correlation ID middleware ─────────────────────────────────────────
if settings.ENABLE_REQUEST_ID_MIDDLEWARE:
    app.add_middleware(RequestContextMiddleware)

# ── Security headers ─────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Rate limiting (slowapi) ──────────────────────────────────────────────────
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from app.core.rate_limiter import limiter  # noqa: E402

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Global error envelope ─────────────────────────────────────────────────────
register_exception_handlers(app)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api/v1")


# ── Built-in health endpoint (fast — DB ping only) ────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    db_ok = False
    stt_ready = None
    vision_ready = None
    tts_ready = None

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(1))
            db_ok = True
    except Exception:
        pass

    try:
        from app.services.whisper_service import model_ready as stt_model_ready
        stt_ready = bool(stt_model_ready())
    except Exception:
        pass

    try:
        from app.services.vision_service import model_ready as vision_model_ready
        vision_ready = bool(vision_model_ready())
    except Exception:
        pass

    try:
        from app.services.tts_service import model_ready as tts_model_ready
        tts_ready = bool(tts_model_ready())
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "stt_ready": stt_ready,
        "vision_ready": vision_ready,
        "tts_ready": tts_ready,
        "env": settings.APP_ENV,
        "version": "2.0.0",
    }
