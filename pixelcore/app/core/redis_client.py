"""
Thin Redis client wrapper — synchronous (used by Celery utilities and health probes).
Lazily creates a single shared connection; safe to call before the event loop starts.
"""
import logging
from typing import Optional

from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Redis] = None


def _redis_url() -> str:
    return (settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://localhost:6379/0").strip()


class RedisClient:
    """Singleton wrapper around the synchronous redis.Redis client."""

    @staticmethod
    def get() -> Redis:
        global _client
        if _client is None:
            _client = Redis.from_url(
                _redis_url(),
                socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
                retry_on_timeout=False,
                decode_responses=True,
            )
        return _client

    @staticmethod
    def ping() -> bool:
        try:
            return bool(RedisClient.get().ping())
        except Exception as exc:
            logger.debug("Redis ping failed: %s", exc)
            return False

    @staticmethod
    def queue_length(queue_name: str = "celery") -> Optional[int]:
        try:
            return int(RedisClient.get().llen(queue_name))
        except Exception as exc:
            logger.debug("Redis queue_length(%s) failed: %s", queue_name, exc)
            return None


# Module-level aliases used by health checks and imported by celery_app
_redis_client_instance = RedisClient()
get_redis_client = RedisClient.get
ping = RedisClient.ping
queue_length = RedisClient.queue_length
