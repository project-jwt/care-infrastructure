# tests/test_summary_recipients.py — GET /api/summaries/:id/recipients
# (the primary's delivery receipt: who a summary was sent to).

from datetime import datetime

from core.security import create_access_token
from models.summary_model import Summary, SummaryRecipient
from models.user_model import User


async def _user(session, *, email, full_name="U", role="primary"):
    # Tokens are minted directly, so a placeholder hash is fine (never checked).
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()  # assign id without ending the transaction
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


async def test_recipients_lists_names_oldest_first(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p@example.com", role="primary")
        alice = await _user(s, email="alice@example.com", full_name="Alice", role="contact")
        bob = await _user(s, email="bob@example.com", full_name="Bob", role="contact")
        summary = Summary(user_id=primary.id, summary_text="hi", transcript="raw")
        s.add(summary)
        await s.flush()
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=alice.id, sent_at=datetime(2026, 1, 1, 9, 0)))
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=bob.id, sent_at=datetime(2026, 1, 2, 9, 0)))
        await s.commit()
        sid = summary.id

    resp = await client.get(f"/api/summaries/{sid}/recipients", headers=_auth(primary))
    assert resp.status_code == 200
    body = resp.json()
    assert [r["fullName"] for r in body] == ["Alice", "Bob"]  # oldest first
    assert body[0]["contactId"] == alice.id
    assert "sentAt" in body[0]


async def test_deleted_recipient_comes_back_null(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p2@example.com", role="primary")
        summary = Summary(user_id=primary.id, summary_text="hi", transcript="raw")
        s.add(summary)
        await s.flush()
        # contact_id NULL = a recipient who has since deleted their account
        # (the SET NULL outcome), which the endpoint must surface, not hide.
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=None, sent_at=datetime(2026, 1, 1, 9, 0)))
        await s.commit()
        sid = summary.id

    resp = await client.get(f"/api/summaries/{sid}/recipients", headers=_auth(primary))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["contactId"] is None
    assert body[0]["fullName"] is None  # frontend renders this as "Deleted user"


async def test_unsent_summary_has_no_recipients(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p3@example.com", role="primary")
        summary = Summary(user_id=primary.id, summary_text="hi")
        s.add(summary)
        await s.flush()
        await s.commit()
        sid = summary.id

    resp = await client.get(f"/api/summaries/{sid}/recipients", headers=_auth(primary))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_other_primarys_summary_is_404(client, sessions):
    async with sessions() as s:
        owner = await _user(s, email="owner@example.com", role="primary")
        intruder = await _user(s, email="intruder@example.com", role="primary")
        summary = Summary(user_id=owner.id, summary_text="secret")
        s.add(summary)
        await s.flush()
        await s.commit()
        sid = summary.id

    # Owner-scoped: another primary gets the same 404 as a nonexistent id.
    resp = await client.get(f"/api/summaries/{sid}/recipients", headers=_auth(intruder))
    assert resp.status_code == 404


async def test_contact_account_is_forbidden(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p4@example.com", role="primary")
        contact = await _user(s, email="c4@example.com", role="contact")
        summary = Summary(user_id=primary.id, summary_text="hi")
        s.add(summary)
        await s.flush()
        await s.commit()
        sid = summary.id

    resp = await client.get(f"/api/summaries/{sid}/recipients", headers=_auth(contact))
    assert resp.status_code == 403  # require_primary


async def test_missing_summary_is_404(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="p5@example.com", role="primary")
        await s.commit()

    resp = await client.get("/api/summaries/999999/recipients", headers=_auth(primary))
    assert resp.status_code == 404
