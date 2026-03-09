"""
One-time migration: add new auth columns to existing tables.
Run once:  python3 migrate_auth_columns.py

Safe to re-run — every ALTER uses IF NOT EXISTS.
"""
import asyncio
import sys

sys.path.insert(0, ".")
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

SQL_STATEMENTS = [
    # ── users table ───────────────────────────────────────────────
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified   BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR NOT NULL DEFAULT 'local'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by    VARCHAR REFERENCES users(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login    TIMESTAMPTZ",

    # ── organisations table ───────────────────────────────────────
    "ALTER TABLE organisations ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE organisations ADD COLUMN IF NOT EXISTS plan        VARCHAR NOT NULL DEFAULT 'free'",
    "ALTER TABLE organisations ADD COLUMN IF NOT EXISTS logo_url    TEXT",

    # Back-fill: mark existing demo users/orgs as verified so they can still log in
    "UPDATE users SET is_verified = TRUE WHERE email IN ('admin@demo.com','hr@demo.com','interviewer@demo.com','candidate@demo.com')",
    "UPDATE organisations SET is_verified = TRUE",
]


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        for sql in SQL_STATEMENTS:
            print(f"\n▶  {sql}")
            await conn.execute(__import__("sqlalchemy").text(sql))
    await engine.dispose()
    print("\n✅  Migration complete — all new auth columns added and back-filled.")


if __name__ == "__main__":
    asyncio.run(main())
