# models/summary_model.py — the summaries + summary_recipients tables
# (spec §Schema Design) + helpers.

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Row, Text, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.contact_model import TrustedContactLink
from models.user_model import User


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


class SummaryRecipient(Base):
    """One 'summary X was sent to contact Y' record (spec: summary_recipients).

    Written by the send feature when an email goes out; read by the contact's
    dashboard. A summary can be sent to many contacts, and a contact can
    receive many summaries — this table is the join between them.
    """

    __tablename__ = "summary_recipients"

    # Python attribute `id`, DB column `recipient_id` — same trick as above.
    id: Mapped[int] = mapped_column("recipient_id", primary_key=True)

    # summary_id CASCADEs: if the summary itself is deleted, its delivery
    # records go with it. contact_id, though, is SET NULL — a receipt must
    # SURVIVE the recipient deleting their account so the sender keeps the
    # record, now reading as "sent to a deleted user" (contact_id IS NULL).
    summary_id: Mapped[int] = mapped_column(
        ForeignKey("summaries.summary_id", ondelete="CASCADE")
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Composite index for the inbox query, which filters on contact_id AND
    # orders by sent_at — Postgres doesn't auto-index FK columns. (create_all
    # only creates MISSING tables: a local DB that already has this one needs
    # the table recreated, or CREATE INDEX by hand, to pick this up.)
    __table_args__ = (Index("ix_summary_recipients_contact_sent", "contact_id", "sent_at"),)


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


async def record_send(
    session: AsyncSession, summary_id: int, contact_ids: list[int]
) -> list[SummaryRecipient]:
    """Record that a summary went out to these contacts (POST /:id/send).

    One row per recipient, all in one commit. contact_ids are deduped here —
    [3, 3] records (and should email) contact 3 once; there's no UNIQUE on
    (summary_id, contact_id) because separate sends of the same summary are
    legitimate re-sends.

    This helper checks neither ownership nor trust, so two obligations on
    the endpoint calling it:
      - it MUST resolve the summary through the owner-scoped find_by_id
        first (spec: 404) — otherwise a caller could record sends of
        someone else's summary;
      - it MUST validate every contact id via contact_model.is_contact_of
        (B2) before any email goes out, so a failed send records nothing.
    """
    # Empty list = no-op (return early). Without this, insert().values([])
    # compiles to "INSERT ... DEFAULT VALUES" — a phantom row that violates
    # the NOT NULL FKs. B5's SendIn min_length=1 guards the endpoint, but the
    # helper stays safe to call with [] on its own.
    if not contact_ids:
        return []

    # One INSERT..RETURNING for the whole batch: recipient_id and the DB-side
    # sent_at come back with the insert itself (a refresh per row would be
    # N+1 extra SELECTs).
    result = await session.execute(
        insert(SummaryRecipient)
        .values([
            {"summary_id": summary_id, "contact_id": contact_id}
            for contact_id in dict.fromkeys(contact_ids)  # dedupe, keep order
        ])
        .returning(SummaryRecipient)
    )
    rows = list(result.scalars().all())
    await session.commit()
    return rows


async def list_received_for_contact(
    session: AsyncSession, contact_id: int
) -> list[Row]:
    """Everything shared WITH a contact, newest send first (GET
    /api/received-summaries). Returns rows of exactly the columns the
    response needs — (summary_id, summary_text, sent_at, sender_id,
    sender_name) — not whole entities: transcript is unbounded TEXT and the
    users row carries password_hash; neither belongs in an inbox query.

    Two joins: recipients -> summaries (what was sent) and summaries ->
    users (who sent it). Scoped by contact_id the same way the owner-scoped
    helpers above are: a contact only ever sees rows addressed to them.
    """
    result = await session.execute(
        select(
            Summary.id.label("summary_id"),
            Summary.summary_text,
            SummaryRecipient.sent_at,
            User.id.label("sender_id"),
            User.full_name.label("sender_name"),
        )
        .join(SummaryRecipient, SummaryRecipient.summary_id == Summary.id)
        .join(User, User.id == Summary.user_id)
        .where(SummaryRecipient.contact_id == contact_id)
        # Postgres now() is transaction-stable: one record_send batch shares
        # a single sent_at, so id breaks the tie and keeps the order stable
        # between refreshes.
        .order_by(SummaryRecipient.sent_at.desc(), SummaryRecipient.id.desc())
    )
    return list(result.all())


async def list_recipients_for_summary(
    session: AsyncSession, summary_id: int
) -> list[Row]:
    """Everyone a summary was sent to, oldest send first — the sender's
    delivery receipt (GET /api/summaries/:id/recipients).

    The name shown is the label the SENDER saved the contact under (the
    nickname on their trusted-contact link, e.g. "Mom"), not the contact's
    own account name — that's how contacts are named everywhere else in the
    app (see frontend displayName). full_name comes back too as the fallback
    for a contact the sender never nicknamed.

    Two outerjoins (LEFT JOINs) so a recipient who has since deleted their
    account still returns a row: contact_id, full_name and nickname all come
    back NULL (the receipt was preserved by ON DELETE SET NULL), which the
    frontend shows as "Deleted user". The nickname is scoped to THIS summary's
    owner via the join to summaries — a contact_id can be trusted by more than
    one primary, so the link is matched on (owner_id, contact_id). Only id +
    names are selected — the full users row (password_hash) never enters the
    query, same as list_received_for_contact.

    Scoping: the CALLER checks the summary belongs to the primary (the router
    does, via find_by_id) before calling this — here we filter only by
    summary_id.
    """
    result = await session.execute(
        select(
            SummaryRecipient.contact_id,
            User.full_name,
            TrustedContactLink.nickname,
            SummaryRecipient.sent_at,
        )
        .join(Summary, Summary.id == SummaryRecipient.summary_id)
        .outerjoin(User, User.id == SummaryRecipient.contact_id)
        .outerjoin(
            TrustedContactLink,
            (TrustedContactLink.contact_id == SummaryRecipient.contact_id)
            & (TrustedContactLink.owner_id == Summary.user_id),
        )
        .where(SummaryRecipient.summary_id == summary_id)
        .order_by(SummaryRecipient.sent_at.asc(), SummaryRecipient.id.asc())
    )
    return list(result.all())
