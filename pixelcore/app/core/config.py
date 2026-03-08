"""
Application configuration.

All settings are read from environment variables (or a .env file).
Required providers are selected at runtime via *_PROVIDER flags so the
system can be reconfigured without code changes.
"""
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "PixelSelect"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # ─── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    INTERVIEW_JOIN_EARLY_SECONDS: int = 0
    INTERVIEW_JOIN_LATE_SECONDS: int = 600

    # ─── Database — PostgreSQL ─────────────────────────────────────────────────
    # asyncpg driver is required:  postgresql+asyncpg://user:pass@host:port/db
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pixelselect"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE: int = 1800  # seconds

    # ─── Email ────────────────────────────────────────────────────────────────
    EMAIL_PROVIDER: str = "log"          # log | sendgrid | smtp
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""

    # ─── LLM provider: groq | ollama | openai | mock ──────────────────────────
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT: float = 30.0
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    OLLAMA_TIMEOUT: float = 60.0
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"  # override for local models
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: float = 30.0

    # ─── Vision provider: deepface | mock ─────────────────────────────────────
    VISION_PROVIDER: str = "deepface"
    VISION_PERSIST_ENABLED: bool = True
    VISION_LOG_SAMPLE_EVERY_N: int = 3  # persist every Nth frame
    ENABLE_VISION_WARMUP: bool = True

    # ─── Speech-to-Text provider: groq | local ────────────────────────────────
    STT_PROVIDER: str = "groq"          # groq = Groq Whisper API; local = faster-whisper on CPU
    STT_MODEL: str = "base"             # faster-whisper size: tiny | base | small | medium
    STT_DEVICE: str = "cpu"
    STT_COMPUTE: str = "int8"
    STT_BEAM_SIZE: int = 2
    STT_VAD_FILTER: bool = True
    STT_VAD_MIN_SILENCE_MS: int = 200
    GROQ_STT_MODEL: str = "whisper-large-v3"
    GROQ_STT_TIMEOUT: float = 20.0

    # ─── Text-to-Speech provider: webspeech | kokoro ──────────────────────────
    # webspeech = frontend browser synthesis fallback; kokoro = local backend TTS
    TTS_PROVIDER: str = "webspeech"
    KOKORO_VOICE: str = "af_heart"
    KOKORO_SPEED: float = 1.0
    ENABLE_TTS_WARMUP: bool = True

    # ─── Local model serving (OpenAI-compatible) ──────────────────────────────
    # When enabled, a /v1/* passthrough is exposed that routes to a local
    # OpenAI-compatible server (e.g. llama.cpp, vLLM, or LM Studio).
    LOCAL_MODEL_SERVER_ENABLED: bool = False
    LOCAL_MODEL_SERVER_URL: str = "http://localhost:8080"  # target server

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: Optional[str] = None
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 1.5
    REDIS_HEALTH_TIMEOUT_SECONDS: float = 1.0
    REDIS_STREAM_DB: int = 0

    # ─── Celery / background tasks ────────────────────────────────────────────
    CELERY_ENABLED: bool = False
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_WAIT_TIMEOUT_SECONDS: float = 3.0
    CELERY_ENQUEUE_TIMEOUT_SECONDS: float = 0.75
    CELERY_SOFT_TIME_LIMIT_SECONDS: int = 25
    CELERY_TIME_LIMIT_SECONDS: int = 35
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_BACKOFF: bool = True
    CELERY_TASK_RETRY_JITTER: bool = True
    CELERY_REALTIME_ENABLED: bool = False
    CELERY_BACKGROUND_ENABLED: bool = True
    CELERY_FALLBACK_COOLDOWN_SECONDS: float = 10.0

    # ─── RTC / Meeting room ───────────────────────────────────────────────────
    RTC_ROOM_CAPACITY: int = 12
    RTC_SIGNAL_TIMEOUT_SECONDS: int = 45
    RTC_JOIN_RATE_LIMIT: int = 6
    RTC_JOIN_WINDOW_SECONDS: int = 30
    RTC_HEARTBEAT_SECONDS: int = 10
    RTC_STALE_PARTICIPANT_TTL_SECONDS: int = 45
    ROOM_BACKEND: str = "auto"          # auto | memory | redis

    # ─── Storage ──────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    RECORDINGS_DIR: str = "recordings"
    UPLOADS_DIR: str = "uploads"
    CANDIDATE_CAN_DOWNLOAD_RECORDINGS: bool = False
    INTERVIEW_LINK_REMINDER_MINUTES: int = 5

    # ─── Feature flags ────────────────────────────────────────────────────────
    AI_LOCAL_FASTPATH_ENABLED: bool = True
    STT_LOCAL_FASTPATH_ENABLED: bool = True
    ENABLE_GLOBAL_ERROR_ENVELOPE: bool = True
    ENABLE_REQUEST_ID_MIDDLEWARE: bool = True
    ENABLE_IDEMPOTENCY: bool = True

    # ─── Seed data ────────────────────────────────────────────────────────────
    SEED_DEMO_DATA: bool = True          # create default users/org on first startup

    # ─── pydantic-settings ────────────────────────────────────────────────────
    model_config = {"env_file": ".env", "extra": "ignore"}

    # ─── Validators ───────────────────────────────────────────────────────────
    @field_validator(
        "DEBUG",
        "CELERY_ENABLED",
        "CELERY_REALTIME_ENABLED",
        "CELERY_BACKGROUND_ENABLED",
        "ENABLE_GLOBAL_ERROR_ENVELOPE",
        "ENABLE_REQUEST_ID_MIDDLEWARE",
        "ENABLE_IDEMPOTENCY",
        "ENABLE_VISION_WARMUP",
        "ENABLE_TTS_WARMUP",
        "VISION_PERSIST_ENABLED",
        "STT_VAD_FILTER",
        "STT_LOCAL_FASTPATH_ENABLED",
        "AI_LOCAL_FASTPATH_ENABLED",
        "DB_POOL_PRE_PING",
        "SEED_DEMO_DATA",
        "LOCAL_MODEL_SERVER_ENABLED",
        "CANDIDATE_CAN_DOWNLOAD_RECORDINGS",
        mode="before",
    )
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "true", "yes", "on"}:
                return True
            if v in {"0", "false", "no", "off"}:
                return False
        return value

    @field_validator("ROOM_BACKEND", mode="before")
    @classmethod
    def _parse_room_backend(cls, value: object) -> str:
        if value is None:
            return "auto"
        v = str(value).strip().lower()
        return v if v in {"auto", "memory", "redis"} else "auto"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
