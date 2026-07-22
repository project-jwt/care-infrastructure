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


# ── PATCH step-up re-auth (email / password require current password) ─────────


async def test_patch_name_only_needs_no_current_password(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="name@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me", json={"fullName": "New Name"}, headers=_auth(user)
    )
    assert resp.status_code == 200
    assert resp.json()["fullName"] == "New Name"


async def test_patch_email_without_current_password_is_403(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="before@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me", json={"email": "after@example.com"}, headers=_auth(user)
    )
    assert resp.status_code == 403
    assert resp.json() == {"message": "Current password is incorrect"}

    # Email is unchanged.
    me = await client.get("/api/users/me", headers=_auth(user))
    assert me.json()["email"] == "before@example.com"


async def test_patch_email_with_wrong_current_password_is_403(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="before2@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me",
        json={"email": "after2@example.com", "currentPassword": "wrong"},
        headers=_auth(user),
    )
    assert resp.status_code == 403


async def test_patch_email_with_correct_current_password_succeeds(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="old@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me",
        json={"email": "new@example.com", "currentPassword": PASSWORD},
        headers=_auth(user),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"


async def test_patch_password_without_current_password_is_403(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="pw@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me", json={"password": "brand-new-pass"}, headers=_auth(user)
    )
    assert resp.status_code == 403


async def test_patch_password_with_correct_current_password_rehashes(client, sessions):
    async with sessions() as s:
        user = await _user(s, email="pw2@example.com")
        await s.commit()

    resp = await client.patch(
        "/api/users/me",
        json={"password": "brand-new-pass", "currentPassword": PASSWORD},
        headers=_auth(user),
    )
    assert resp.status_code == 200

    # The new password now authenticates via login; the old one no longer does.
    ok = await client.post(
        "/api/auth/login", json={"email": "pw2@example.com", "password": "brand-new-pass"}
    )
    assert ok.status_code == 200
    stale = await client.post(
        "/api/auth/login", json={"email": "pw2@example.com", "password": PASSWORD}
    )
    assert stale.status_code == 401


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


async def test_contact_deletion_preserves_receipt_as_deleted_user(session):
    # When the RECIPIENT deletes their account, the sender's delivery record
    # must survive — contact_id set NULL ("sent to a deleted user") — while the
    # trusted-contact link (who can I send to now) is removed.
    await session.execute(text("PRAGMA foreign_keys=ON"))

    owner = await _user(session, email="sender@example.com", role="primary")
    contact = await _user(session, email="leaving@example.com", role="contact")

    summary = Summary(user_id=owner.id, summary_text="a summary", transcript="raw")
    session.add(summary)
    await session.flush()
    session.add(SummaryRecipient(summary_id=summary.id, contact_id=contact.id))
    session.add(TrustedContactLink(owner_id=owner.id, contact_id=contact.id))
    await session.commit()

    removed = await user_model.delete(session, contact.id)
    assert removed is True

    session.expunge_all()

    async def count(model):
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar()

    # The sender's summary is untouched, and the receipt survives with its
    # recipient nulled out — the sender still knows a send happened.
    assert await session.get(Summary, summary.id) is not None
    assert await count(SummaryRecipient) == 1
    result = await session.execute(select(SummaryRecipient.contact_id))
    assert result.scalar() is None
    # The deleted user drops off the sender's trusted-contacts list, though.
    assert await count(TrustedContactLink) == 0


async def test_delete_missing_user_returns_false(session):
    assert await user_model.delete(session, 999999) is False
