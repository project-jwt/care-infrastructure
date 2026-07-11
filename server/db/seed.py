# db/seed.py — reference rows the app expects to exist (spec MVP §4: the
# pre-loaded helplines).
#
# Two entry points, one source of truth:
#   - main.py's lifespan calls ensure_seeded() after create_all, so a fresh
#     database (teammate setup, Render deploy) seeds itself with no manual step
#   - `python -m db.seed` (from server/) does create_all + seed standalone
#
# ensure_seeded is idempotent by design: it only inserts when the table is
# EMPTY. That means restarts never duplicate rows, and rows added later by
# hand are never fought with — this is "make sure there's something", not a
# sync tool.

import asyncio

from sqlalchemy import func, select
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
    """Insert the pre-loaded helplines iff the table is empty."""
    count = (
        await session.execute(select(func.count()).select_from(Helpline))
    ).scalar()
    if count:
        return
    session.add_all([Helpline(**row) for row in HELPLINES])
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
