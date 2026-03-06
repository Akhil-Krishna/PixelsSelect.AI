"""
Test Redis connection.
Run: python test_redis.py
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

print("=" * 50)
print("TEST: Redis")
print("=" * 50)
print(f"URL: {REDIS_URL}")


async def test_redis():
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(REDIS_URL, decode_responses=True)

        pong = await client.ping()
        print(f"✅ Redis ping: {pong}")

        await client.set("hireai_test_key", "hello_from_hireai", ex=10)
        val = await client.get("hireai_test_key")
        print(f"✅ Set/Get test: {val!r}")

        await client.delete("hireai_test_key")
        print("✅ Delete test passed")

        await client.aclose()
        print("✅ Connection closed cleanly")

    except Exception as e:
        print(f"❌ Redis FAILED: {e}")
        print("\nMake sure Docker container is running:")
        print("  docker start hireai-redis")


asyncio.run(test_redis())
print("\nRedis test done.")