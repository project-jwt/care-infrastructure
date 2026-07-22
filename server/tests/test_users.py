# tests/test_users.py — account deletion (DELETE /api/users/me).
#
# What the manual run can't easily prove and what's easy to regress:
#   - the password re-auth gate (correct -> 204, wrong -> 403, none -> 401)
#   - a deleted account's token stops working immediately
#   - the ON DELETE CASCADE actually clears the account's owned rows
#
# The HTTP tests run against SQLite (like the rest of the suite). SQLite only
# enforces foreign keys — and therefore ON DELETE CASCADE — when
# PRAGMA foreign_keys=ON is set per connection, so the cascade test turns it
# on explicitly; prod Postgres enforces it unconditionally.

from sqlalchemy import func, select, text

from core.security import create_access_token, hash_password
from models import user_model
from models.summary_model import Summary, SummaryRecipient
from models.contact_model import TrustedContactLink
from models.user_model import User

PASSWORD = "correct horse battery"  # >= 8 chars, matches the register floor


async def _user(session, *, email, role="primary", password=PASSWORD):
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
    )
    session.add(user)
    await session.flush()  # assign the id without ending the transaction
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ── HTTP endpoint ────────────────────────────────────────────────────────────


async def test_delete_me_wrong_password_is_403_and_keeps_account(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="keep@example.com")
        await s.commit()

    resp = await client.request(
        "DELETE", "/api/users/me", json={"password": "not my password"}, headers=_auth(user)
    )
    assert resp.status_code == 403
    assert resp.json() == {"message": "Incorrect password"}

    # The account is untouched — the token still resolves.
    still = await client.get("/api/users/me", headers=_auth(user))
    assert still.status_code == 200


async def test_delete_me_requires_authentication(client):
    resp = await client.request("DELETE", "/api/users/me", json={"password": PASSWORD})
    assert resp.status_code == 401


async def test_delete_me_success_removes_account_and_invalidates_token(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="gone@example.com")
        await s.commit()

    resp = await client.request(
        "DELETE", "/api/users/me", json={"password": PASSWORD}, headers=_auth(user)
    )
    assert resp.status_code == 204
    assert resp.content == b""  # 204 has no body

    # Same (cryptographically valid) token now points at a gone account -> 401.
    after = await client.get("/api/users/me", headers=_auth(user))
    assert after.status_code == 401


# ── Model layer: cascade ─────────────────────────────────────────────────────


async def test_delete_cascades_to_owned_rows(session):
    # SQLite enforces FKs (and thus cascade) only with this pragma on.
    await session.execute(text("PRAGMA foreign_keys=ON"))

    owner = await _user(session, email="owner@example.com", role="primary")
    contact = await _user(session, email="contact@example.com", role="contact")

    summary = Summary(user_id=owner.id, summary_text="a summary", transcript="raw")
    session.add(summary)
    await session.flush()
    session.add(SummaryRecipient(summary_id=summary.id, contact_id=contact.id))
    session.add(TrustedContactLink(owner_id=owner.id, contact_id=contact.id))
    await session.commit()

    removed = await user_model.delete(session, owner.id)
    assert removed is True

    # Drop the identity-map cache so these reads hit the DB, not stale Python
    # objects (cascade happens in the database, not the ORM session).
    session.expunge_all()

    async def count(model):
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar()

    # Deleting the owner cascades to their summary, its delivery record, and
    # the contact link they own.
    assert await count(Summary) == 0
    assert await count(SummaryRecipient) == 0
    assert await count(TrustedContactLink) == 0
    # The contact account itself is NOT theirs to delete — it survives.
    assert await session.get(User, contact.id) is not None


async def test_delete_missing_user_returns_false(session):
    assert await user_model.delete(session, 999999) is False
