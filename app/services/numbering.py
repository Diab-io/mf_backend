"""
Generates Repair Request IDs in the form RR-2026-0001.

Uses a Postgres advisory lock keyed by year so concurrent requests can't
collide on the same sequence number, without needing a separate counter
table or a DB sequence per year.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repair_request import RepairRequest

_LOCK_NAMESPACE = 911_001  # arbitrary fixed namespace for this lock class


async def generate_request_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year

    # Advisory lock scoped to (namespace, year) — released automatically at
    # transaction end. Serializes number generation across concurrent requests.
    # Postgres-only; skipped on other dialects (e.g. SQLite in tests), where
    # the test suite runs single-threaded anyway so the race doesn't occur.
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:ns, :key)"), {"ns": _LOCK_NAMESPACE, "key": year})

    prefix = f"RR-{year}-"
    result = await db.execute(
        select(func.count()).select_from(RepairRequest).where(RepairRequest.request_number.like(f"{prefix}%"))
    )
    count = result.scalar_one()
    next_seq = count + 1
    return f"{prefix}{next_seq:04d}"
