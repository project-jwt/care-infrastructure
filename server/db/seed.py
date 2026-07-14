# db/seed.py — reference rows the app expects to exist (spec MVP §4: the
# pre-loaded helplines).
#
# Two entry points, one source of truth:
#   - main.py's lifespan calls ensure_seeded() after create_all, so a fresh
#     database (teammate setup, Render deploy) seeds itself with no manual step
#   - `python -m db.seed` (from server/) does create_all + seed standalone
#
# ensure_seeded is idempotent per row: it inserts any listed helpline whose
# name isn't in the table yet. Restarts never duplicate rows, rows edited by
# hand are never overwritten (matching is by name only, nothing is updated or
# deleted) — and a row added to HELPLINES later reaches every existing
# database, including production, on its next boot.
#
# Known limitation: the check-then-insert isn't atomic, so two workers booting
# at the same instant could both insert the same row. Not reachable today
# (Render runs WEB_CONCURRENCY=1); if we ever scale workers, switch to an
# ON CONFLICT upsert keyed on name.

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base
from db.engine import AsyncSessionLocal, engine
from models.helpline_model import Helpline

# The spec's MVP helpline. More rows (emotional support, resource lines) are
# a paid-stretch feature — they get added HERE when that ticket lands.
HELPLINES = [
    {
        "name": "AARP Fraud Watch Network Helpline",
        "phone": "877-908-3360",  # display form; the frontend builds the tel: link
        "hours": "Monday to Friday, 8am to 8pm ET",
        "description": (
            "Free help from trained volunteers who can tell you whether "
            "something is a scam and what to do next."
        ),
    },
]


async def ensure_seeded(session: AsyncSession) -> None:
    """Insert any pre-loaded helpline not already present (matched by name)."""
    existing = set((await session.execute(select(Helpline.name))).scalars())
    missing = [row for row in HELPLINES if row["name"] not in existing]
    if not missing:
        return
    session.add_all([Helpline(**row) for row in missing])
    await session.commit()


async def main() -> None:
    # Standalone runner: same create_all main.py does at startup, then seed.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await ensure_seeded(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
