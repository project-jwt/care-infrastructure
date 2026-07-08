# models/summary_model.py — the summaries table (spec §Schema Design) + helpers
#
# TODO (built with the send feature): summary_recipients table and its helpers
#   - record_send(session, summary_id, contact_ids)
#   - list_received_for_contact(session, contact_id)

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Summary(Base):
    __tablename__ = "summaries"

    # Same trick as User: Python attribute `id`, DB column `summary_id`.
    id: Mapped[int] = mapped_column("summary_id", primary_key=True)

    # Our first FOREIGN KEY — Postgres enforces that every summary belongs to
    # a real user (inserting user_id=999 fails at the DB, like UNIQUE did for
    # emails). ondelete="CASCADE": deleting a user deletes their summaries.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    # Nullable (spec: transcript TEXT, no NOT NULL) — Mapped[str | None] is
    # how a column opts out of NOT NULL. A summary can be saved without the
    # raw transcript.
    transcript: Mapped[str | None] = mapped_column(Text)

    summary_text: Mapped[str] = mapped_column(Text)  # TEXT NOT NULL

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # onupdate=func.now(): SQLAlchemy adds updated_at = now() to the SET clause
    # of every UPDATE touching this row — PATCH bumps it with no router code.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Query helpers ────────────────────────────────────────────────────────────
# OWNERSHIP SCOPING: every single-record helper takes user_id alongside the
# record id and ANDs both into the WHERE. A summary that exists but belongs to
# someone else returns the SAME None as one that doesn't exist — the router
# turns both into 404, so the API never confirms another user's data exists
# (spec §API Contract). Don't "optimize" the user_id conditions away.


async def create(
    session: AsyncSession, user_id: int, transcript: str | None, summary_text: str
) -> Summary:
    """Insert a finalized summary for a user (POST /api/summaries)."""
    summary = Summary(user_id=user_id, transcript=transcript, summary_text=summary_text)
    session.add(summary)
    await session.commit()
    await session.refresh(summary)  # pull back id, created_at, updated_at
    return summary


async def list_by_user(session: AsyncSession, user_id: int) -> list[Summary]:
    """All of one user's summaries, newest first (GET /api/summaries)."""
    result = await session.execute(
        select(Summary)
        .where(Summary.user_id == user_id)
        .order_by(Summary.created_at.desc())  # spec: newest first
    )
    return list(result.scalars().all())


async def find_by_id(session: AsyncSession, summary_id: int, user_id: int) -> Summary | None:
    """One summary — only if it belongs to user_id (see scoping note above)."""
    result = await session.execute(
        select(Summary).where(Summary.id == summary_id, Summary.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_text(
    session: AsyncSession, summary_id: int, user_id: int, summary_text: str
) -> Summary | None:
    """Edit a summary's text (PATCH /api/summaries/:id). updated_at bumps
    automatically via the column's onupdate."""
    summary = await find_by_id(session, summary_id, user_id)  # scoped lookup
    if summary is None:
        return None
    summary.summary_text = summary_text
    await session.commit()
    await session.refresh(summary)  # pick up the DB-side updated_at
    return summary


async def delete(session: AsyncSession, summary_id: int, user_id: int) -> bool:
    """Delete a summary (DELETE /api/summaries/:id). True if deleted,
    False if not found / not owned — router turns False into 404."""
    summary = await find_by_id(session, summary_id, user_id)  # scoped lookup
    if summary is None:
        return False
    await session.delete(summary)  # queued in the session's deleted bucket
    await session.commit()         # DELETE FROM summaries WHERE ... runs here
    return True
