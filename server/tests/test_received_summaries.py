# tests/test_received_summaries.py — the contact inbox (B5).
#
# Covers the two pieces added for the send feature's read path:
#   - summary_model.record_send + list_received_for_contact (model layer)
#   - GET /api/received-summaries (router shape + require_contact gate)
# The one thing the manual acceptance run couldn't reach was rows rendering
# through the lean query into the contract shape — that's the focus here.

from datetime import datetime

from core.security import create_access_token
from models import summary_model
from models.summary_model import Summary, SummaryRecipient
from models.user_model import User


async def _user(session, *, email, full_name, role):
    # password_hash is NOT NULL but never checked here (we mint tokens directly),
    # so a placeholder string beats paying for a real bcrypt hash.
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()  # assign the id without ending the transaction
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ── Model layer ──────────────────────────────────────────────────────────────


async def test_record_send_dedupes_and_roundtrips(session):
    sender = await _user(session, email="p@example.com", full_name="Prim", role="primary")
    alice = await _user(session, email="a@example.com", full_name="Alice", role="contact")
    bob = await _user(session, email="b@example.com", full_name="Bob", role="contact")
    summary = Summary(user_id=sender.id, summary_text="the summary", transcript="raw")
    session.add(summary)
    await session.flush()

    # Duplicate alice id collapses to one row; the write goes through the real
    # INSERT..RETURNING path record_send now uses.
    rows = await summary_model.record_send(session, summary.id, [alice.id, alice.id, bob.id])
    assert len(rows) == 2

    inbox = await summary_model.list_received_for_contact(session, alice.id)
    assert len(inbox) == 1
    row = inbox[0]
    assert row.summary_id == summary.id
    assert row.summary_text == "the summary"
    assert row.sender_id == sender.id
    assert row.sender_name == "Prim"
    # The projection deliberately doesn't carry transcript (unbounded) or any
    # user column beyond id/name — so those attributes aren't on the row at all.
    assert not hasattr(row, "transcript")
    assert not hasattr(row, "password_hash")


# ── HTTP endpoint ────────────────────────────────────────────────────────────


async def test_inbox_shape_and_newest_first(client, sessions):
    async with sessions() as s:
        sender = await _user(s, email="sender@example.com", full_name="Sender Name", role="primary")
        contact = await _user(s, email="c@example.com", full_name="Contact", role="contact")
        older = Summary(user_id=sender.id, summary_text="older one", transcript="raw-older")
        newer = Summary(user_id=sender.id, summary_text="newer one", transcript="raw-newer")
        s.add_all([older, newer])
        await s.flush()
        s.add_all([
            SummaryRecipient(summary_id=older.id, contact_id=contact.id, sent_at=datetime(2026, 1, 1, 9, 0)),
            SummaryRecipient(summary_id=newer.id, contact_id=contact.id, sent_at=datetime(2026, 1, 2, 9, 0)),
        ])
        await s.commit()
        contact_tok = _auth(contact)
        newer_id, older_id, sender_id = newer.id, older.id, sender.id

    resp = await client.get("/api/received-summaries", headers=contact_tok)
    assert resp.status_code == 200
    data = resp.json()

    # Newest send first.
    assert [item["summaryId"] for item in data] == [newer_id, older_id]

    # Exact contract shape — no transcript, from is {id, fullName}. images is
    # part of the contract now (empty here — nothing attached to these).
    first = data[0]
    assert set(first) == {"summaryId", "summaryText", "sentAt", "from", "images"}
    assert first["summaryText"] == "newer one"
    assert first["from"] == {"id": sender_id, "fullName": "Sender Name"}
    assert first["images"] == []

    # The sender's private fields must never appear anywhere in the payload.
    assert "sender@example.com" not in resp.text
    assert "transcript" not in resp.text
    assert "raw-newer" not in resp.text


async def test_inbox_tiebreaker_orders_by_recipient_id_desc(client, sessions):
    # Postgres now() is transaction-stable, so a single record_send batch shares
    # one sent_at; the query breaks the tie on recipient_id desc. Same sent_at
    # on two rows here proves that tiebreaker is deterministic.
    async with sessions() as s:
        sender = await _user(s, email="s2@example.com", full_name="S2", role="primary")
        contact = await _user(s, email="c2@example.com", full_name="C2", role="contact")
        first_summary = Summary(user_id=sender.id, summary_text="A")
        second_summary = Summary(user_id=sender.id, summary_text="B")
        s.add_all([first_summary, second_summary])
        await s.flush()
        same = datetime(2026, 3, 3, 12, 0)
        # Insert A then B, so B's recipient_id is higher.
        s.add(SummaryRecipient(summary_id=first_summary.id, contact_id=contact.id, sent_at=same))
        await s.flush()
        s.add(SummaryRecipient(summary_id=second_summary.id, contact_id=contact.id, sent_at=same))
        await s.commit()
        tok = _auth(contact)

    resp = await client.get("/api/received-summaries", headers=tok)
    assert resp.status_code == 200
    # Later-inserted (higher recipient_id) comes first despite the equal sent_at.
    assert [item["summaryText"] for item in resp.json()] == ["B", "A"]


async def test_inbox_scoped_per_contact(client, sessions):
    async with sessions() as s:
        sender = await _user(s, email="s3@example.com", full_name="S3", role="primary")
        addressed = await _user(s, email="has@example.com", full_name="Has Mail", role="contact")
        empty = await _user(s, email="none@example.com", full_name="No Mail", role="contact")
        summary = Summary(user_id=sender.id, summary_text="only for addressed")
        s.add(summary)
        await s.flush()
        s.add(SummaryRecipient(summary_id=summary.id, contact_id=addressed.id, sent_at=datetime(2026, 4, 1, 8, 0)))
        await s.commit()
        addressed_tok, empty_tok = _auth(addressed), _auth(empty)

    assert len(((await client.get("/api/received-summaries", headers=addressed_tok)).json())) == 1
    # A contact nobody sent to sees an empty list, not the other contact's row.
    empty_resp = await client.get("/api/received-summaries", headers=empty_tok)
    assert empty_resp.status_code == 200
    assert empty_resp.json() == []


async def test_inbox_rejects_primary_and_anonymous(client, sessions):
    async with sessions() as s:
        primary = await _user(s, email="prim@example.com", full_name="Prim", role="primary")
        await s.commit()
        primary_tok = _auth(primary)

    # Right auth, wrong role -> 403 in the spec's { message } shape.
    forbidden = await client.get("/api/received-summaries", headers=primary_tok)
    assert forbidden.status_code == 403
    assert forbidden.json() == {"message": "Contact account required"}

    # No token at all -> 401.
    anon = await client.get("/api/received-summaries")
    assert anon.status_code == 401
    assert "message" in anon.json()
