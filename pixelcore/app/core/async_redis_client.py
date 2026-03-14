"""
Async Redis client wrapper with connection pooling.
Used for async operations like token blocklist checks in FastAPI dependencies.
"""
import logging
from typing import Optional

from redis.asyncio import Redis, ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


def _redis_url() -> str:
    return (settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://localhost:6379/0").strip()


async def get_async_redis_pool() -> ConnectionPool:
    """Get or create the async Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            _redis_url(),
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            retry_on_timeout=False,
            decode_responses=True,
            max_connections=20,  # Connection pool for better performance
        )
    return _pool


class AsyncRedisClient:
    """Singleton wrapper around the async redis.asyncio.Redis client with connection pooling."""

    @staticmethod
    async def get() -> Redis:
        global _client
        if _client is None:
            pool = await get_async_redis_pool()
            _client = Redis(connection_pool=pool)
        return _client

    @staticmethod
    async def ping() -> bool:
        try:
            client = await AsyncRedisClient.get()
            return await client.ping()
        except Exception as exc:
            logger.debug("Async Redis ping failed: %s", exc)
            return False

    @staticmethod
    async def exists(key: str) -> int:
        """Check if a key exists in Redis."""
        try:
            client = await AsyncRedisClient.get()
            return await client.exists(key)
        except Exception as exc:
            logger.debug("Async Redis exists(%s) failed: %s", key, exc)
            return 0

    @staticmethod
    async def setex(key: str, time: int, value: str) -> bool:
        """Set a key with expiration time."""
        try:
            client = await AsyncRedisClient.get()
            return await client.setex(key, time, value)
        except Exception as exc:
            logger.debug("Async Redis setex(%s) failed: %s", key, exc)
            return False

    @staticmethod
    async def get_value(key: str) -> Optional[str]:
        """Get a value by key."""
        try:
            client = await AsyncRedisClient.get()
            return await client.get(key)
        except Exception as exc:
            logger.debug("Async Redis get(%s) failed: %s", key, exc)
            return None

    @staticmethod
    async def delete(key: str) -> int:
        """Delete a key."""
        try:
            client = await AsyncRedisClient.get()
            return await client.delete(key)
        except Exception as exc:
            logger.debug("Async Redis delete(%s) failed: %s", key, exc)
            return 0

    @staticmethod
    async def queue_length(queue_name: str = "celery") -> Optional[int]:
        try:
            client = await AsyncRedisClient.get()
            return await client.llen(queue_name)
        except Exception as exc:
            logger.debug("Async Redis queue_length(%s) failed: %s", queue_name, exc)
            return None


# Module-level async functions for convenience
async_redis_client = AsyncRedisClient()
get_async_redis = AsyncRedisClient.get
async_ping = AsyncRedisClient.ping
async_exists = AsyncRedisClient.exists
async_setex = AsyncRedisClient.setex
async_get_value = AsyncRedisClient.get_value
async_delete = AsyncRedisClient.delete
async_queue_length = AsyncRedisClient.queue_length
