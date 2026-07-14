# models/helpline_model.py — the helplines table (spec §Schema Design) + helpers.
#
# Pre-loaded, read-only reference data (spec MVP §4): the app never lets a
# user write to this table — rows come from db/seed.py. That's why the only
# helper is list_all: no ownership scoping, no create/update/delete.

from sqlalchemy import Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Helpline(Base):
    __tablename__ = "helplines"

    # Same trick as User/Summary: Python attribute `id`, DB column `helpline_id`.
    id: Mapped[int] = mapped_column("helpline_id", primary_key=True)

    name: Mapped[str] = mapped_column(Text)   # TEXT NOT NULL
    # Display form ("877-908-3360") — the frontend derives the tel: link from
    # it, so the DB stores what humans should read.
    phone: Mapped[str] = mapped_column(Text)  # TEXT NOT NULL

    # Nullable per spec: a line without published hours (or blurb) is fine.
    hours: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


# ── Query helpers ────────────────────────────────────────────────────────────


async def list_all(session: AsyncSession) -> list[Helpline]:
    """Every helpline, in seed order (GET /api/helplines)."""
    result = await session.execute(select(Helpline).order_by(Helpline.id))
    return list(result.scalars().all())
