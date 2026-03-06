"""
Test PostgreSQL connection via asyncpg.
Run: python test_db.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/pixelselect"
)

print("=" * 50)
print("TEST: PostgreSQL via asyncpg")
print("=" * 50)
print(f"URL: {DATABASE_URL.split('@')[-1]}")  # hide credentials


async def test_db():
    import asyncpg

    # asyncpg uses different URL format (no +asyncpg prefix)
    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(url)
        print("✅ Connected to PostgreSQL")

        version = await conn.fetchval("SELECT version();")
        print(f"   Version: {version[:50]}")

        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        if tables:
            print(f"   Tables found: {[t['tablename'] for t in tables]}")
        else:
            print("   No tables yet (run the app once to create them)")

        await conn.close()
        print("✅ Connection closed cleanly")

    except Exception as e:
        print(f"❌ PostgreSQL FAILED: {e}")
        print("\nMake sure Docker container is running:")
        print("  docker start hireai-postgres")


asyncio.run(test_db())
print("\nDB test done.")