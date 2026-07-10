# models/contact_model.py — the trusted_contact_links table (spec §Schema
# Design) + helpers.
#
# This is a LINK table: it doesn't store people, it stores "primary user X
# trusts contact user Y" edges between two rows of users. Both ends are FKs,
# so a contact must already have an account before they can be linked (spec
# decision: contacts are registered users, added by email).

from sqlalchemy import ForeignKey, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.user_model import User


class TrustedContactLink(Base):
    __tablename__ = "trusted_contact_links"

    # Python attribute `id`, DB column `link_id` — same trick as User/Summary.
    id: Mapped[int] = mapped_column("link_id", primary_key=True)

    # Two FKs into the SAME table: the primary user who owns the list, and
    # the contact-role user they trust. CASCADE on both ends — deleting
    # either account dissolves the link.
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    # Both optional labels the owner puts on the link ("Mom", "my son").
    nickname: Mapped[str | None] = mapped_column(Text)
    relationship: Mapped[str | None] = mapped_column(Text)

    # Spec: UNIQUE (owner_id, contact_id) — you can't add the same contact
    # twice. Like the email UNIQUE in auth, the router translates the
    # IntegrityError from a race into a 409.
    __table_args__ = (UniqueConstraint("owner_id", "contact_id"),)


# ── Query helpers ────────────────────────────────────────────────────────────
# OWNERSHIP SCOPING (same rule as summary_model): single-record helpers AND
# owner_id into the WHERE, so someone else's link_id returns the same None as
# a nonexistent one — the router 404s both identically.
#
# The contract's response shape needs the contact's fullName/email, which live
# on users, so the read helpers return (link, contact_user) pairs from a JOIN
# rather than bare links.


async def list_by_owner(
    session: AsyncSession, owner_id: int
) -> list[tuple[TrustedContactLink, User]]:
    """All of one primary user's links, with each contact's user row joined in
    (GET /api/contacts)."""
    result = await session.execute(
        select(TrustedContactLink, User)
        .join(User, User.id == TrustedContactLink.contact_id)
        .where(TrustedContactLink.owner_id == owner_id)
        .order_by(TrustedContactLink.id)
    )
    return [(link, user) for link, user in result.all()]


async def create(
    session: AsyncSession,
    owner_id: int,
    contact_id: int,
    nickname: str | None,
    relationship: str | None,
) -> TrustedContactLink:
    """Insert a link (POST /api/contacts). Raises IntegrityError on a
    duplicate (owner_id, contact_id) — the router maps it to 409."""
    link = TrustedContactLink(
        owner_id=owner_id,
        contact_id=contact_id,
        nickname=nickname,
        relationship=relationship,
    )
    session.add(link)
    # No refresh needed: the INSERT's RETURNING already populated link.id at
    # flush, and this table has no other server-generated columns (unlike
    # summaries' onupdate timestamp).
    await session.commit()
    return link


async def find_by_link_id(
    session: AsyncSession, link_id: int, owner_id: int
) -> tuple[TrustedContactLink, User] | None:
    """One link + its contact's user row — only if owner_id owns it."""
    result = await session.execute(
        select(TrustedContactLink, User)
        .join(User, User.id == TrustedContactLink.contact_id)
        .where(TrustedContactLink.id == link_id, TrustedContactLink.owner_id == owner_id)
    )
    row = result.first()
    return (row[0], row[1]) if row else None


async def update(
    session: AsyncSession, link_id: int, owner_id: int, **fields
) -> tuple[TrustedContactLink, User] | None:
    """Edit nickname/relationship (PATCH /api/contacts/:linkId). Only the
    fields passed get set — the router sends exclude_unset fields, so a PATCH
    that omits nickname leaves it alone rather than nulling it.

    Known narrow race (noted, not handled): a concurrent DELETE landing
    between our SELECT and this UPDATE makes SQLAlchemy raise StaleDataError
    (a 500) — the loser of that race was getting an error either way."""
    row = await find_by_link_id(session, link_id, owner_id)  # scoped lookup
    if row is None:
        return None
    link, contact_user = row
    for name, value in fields.items():
        setattr(link, name, value)
    # No refresh: no server-generated columns to re-fetch on this table.
    await session.commit()
    return link, contact_user


async def delete(session: AsyncSession, link_id: int, owner_id: int) -> bool:
    """Remove a link (DELETE /api/contacts/:linkId). True if deleted,
    False if not found / not owned — router turns False into 404."""
    row = await find_by_link_id(session, link_id, owner_id)  # scoped lookup
    if row is None:
        return False
    await session.delete(row[0])
    await session.commit()
    return True


async def is_contact_of(session: AsyncSession, owner_id: int, contact_id: int) -> bool:
    """Does a link owner_id -> contact_id exist? The send feature uses this to
    reject summary recipients who aren't the sender's trusted contacts."""
    result = await session.execute(
        select(TrustedContactLink.id).where(
            TrustedContactLink.owner_id == owner_id,
            TrustedContactLink.contact_id == contact_id,
        )
    )
    return result.scalar_one_or_none() is not None
