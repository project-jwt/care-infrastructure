# tests/test_send_summary.py — POST /api/summaries/:id/send.
#
# The send route's partial-success contract is what these tests pin down:
# every recipient gets an attempt, successes are recorded in
# summary_recipients and returned in sentTo, provider failures come back in
# `failed`, and 502 is reserved for the nothing-went-out case. The email
# provider itself is faked at the router's import site — no Resend traffic.

from sqlalchemy import select

from core.email import EmailSendError
from core.security import create_access_token
from models.contact_model import TrustedContactLink
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


async def _seed(sessions):
    """One primary with a saved summary and two trusted contacts. Returns the
    ids and auth header the HTTP tests need (captured before the session
    closes, so nothing touches expired ORM objects afterwards)."""
    async with sessions() as s:
        sender = await _user(s, email="p@example.com", full_name="Prim", role="primary")
        alice = await _user(s, email="alice@example.com", full_name="Alice", role="contact")
        bob = await _user(s, email="bob@example.com", full_name="Bob", role="contact")
        summary = Summary(user_id=sender.id, summary_text="the summary")
        s.add(summary)
        await s.flush()
        s.add_all([
            TrustedContactLink(owner_id=sender.id, contact_id=alice.id),
            TrustedContactLink(owner_id=sender.id, contact_id=bob.id),
        ])
        await s.commit()
        return {
            "auth": _auth(sender),
            "summary_id": summary.id,
            "alice_id": alice.id,
            "bob_id": bob.id,
        }


def _fake_send(fail_for: set[str]):
    """A send_summary_email stand-in that fails for the given recipient
    emails and records every attempt, so tests can assert nobody is skipped."""
    attempted = []

    async def fake(to_email, summary_text, from_name=None):
        attempted.append(to_email)
        if to_email in fail_for:
            raise EmailSendError("provider rejected the address")

    return fake, attempted


async def _recorded_contact_ids(sessions, summary_id):
    async with sessions() as s:
        result = await s.execute(
            select(SummaryRecipient.contact_id).where(
                SummaryRecipient.summary_id == summary_id
            )
        )
        return sorted(result.scalars().all())


async def test_all_succeed(client, sessions, monkeypatch):
    seed = await _seed(sessions)
    fake, attempted = _fake_send(fail_for=set())
    # Patch where the router looks the name up, not where it's defined —
    # routers/summaries.py imported the function directly.
    monkeypatch.setattr("routers.summaries.send_summary_email", fake)

    resp = await client.post(
        f"/api/summaries/{seed['summary_id']}/send",
        json={"contactIds": [seed["alice_id"], seed["bob_id"]]},
        headers=seed["auth"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summaryId"] == seed["summary_id"]
    assert [item["contactId"] for item in data["sentTo"]] == [seed["alice_id"], seed["bob_id"]]
    assert data["failed"] == []
    assert attempted == ["alice@example.com", "bob@example.com"]
    assert await _recorded_contact_ids(sessions, seed["summary_id"]) == sorted(
        [seed["alice_id"], seed["bob_id"]]
    )


async def test_partial_failure_records_only_successes(client, sessions, monkeypatch):
    seed = await _seed(sessions)
    fake, attempted = _fake_send(fail_for={"alice@example.com"})
    monkeypatch.setattr("routers.summaries.send_summary_email", fake)

    resp = await client.post(
        f"/api/summaries/{seed['summary_id']}/send",
        json={"contactIds": [seed["alice_id"], seed["bob_id"]]},
        headers=seed["auth"],
    )
    # Partial send is a success with a failed list, NOT a 502 — the client
    # needs to know Bob got it and only Alice needs a retry.
    assert resp.status_code == 200
    data = resp.json()
    assert [item["contactId"] for item in data["sentTo"]] == [seed["bob_id"]]
    assert data["failed"] == [{"contactId": seed["alice_id"]}]
    # Alice's failure must not stop Bob's attempt.
    assert attempted == ["alice@example.com", "bob@example.com"]
    # Only the delivered email lands in summary_recipients — a recorded row
    # is what the contact dashboard shows, so it must mean a real delivery.
    assert await _recorded_contact_ids(sessions, seed["summary_id"]) == [seed["bob_id"]]


async def test_all_fail_is_502_and_records_nothing(client, sessions, monkeypatch):
    seed = await _seed(sessions)
    fake, attempted = _fake_send(fail_for={"alice@example.com", "bob@example.com"})
    monkeypatch.setattr("routers.summaries.send_summary_email", fake)

    resp = await client.post(
        f"/api/summaries/{seed['summary_id']}/send",
        json={"contactIds": [seed["alice_id"], seed["bob_id"]]},
        headers=seed["auth"],
    )
    # Nothing went out -> the old outage semantics hold: 502, no rows, and a
    # plain retry of the same request is safe.
    assert resp.status_code == 502
    assert attempted == ["alice@example.com", "bob@example.com"]
    assert await _recorded_contact_ids(sessions, seed["summary_id"]) == []


async def test_untrusted_contact_is_403_before_any_email(client, sessions, monkeypatch):
    seed = await _seed(sessions)
    async with sessions() as s:
        stranger = await _user(s, email="x@example.com", full_name="X", role="contact")
        await s.commit()
        stranger_id = stranger.id
    fake, attempted = _fake_send(fail_for=set())
    monkeypatch.setattr("routers.summaries.send_summary_email", fake)

    resp = await client.post(
        f"/api/summaries/{seed['summary_id']}/send",
        json={"contactIds": [seed["alice_id"], stranger_id]},
        headers=seed["auth"],
    )
    assert resp.status_code == 403
    # Validation runs before the send loop — one bad id means zero emails.
    assert attempted == []
    assert await _recorded_contact_ids(sessions, seed["summary_id"]) == []


async def test_someone_elses_summary_is_404(client, sessions, monkeypatch):
    seed = await _seed(sessions)
    async with sessions() as s:
        other = await _user(s, email="other@example.com", full_name="Other", role="primary")
        await s.commit()
        other_auth = _auth(other)
    fake, attempted = _fake_send(fail_for=set())
    monkeypatch.setattr("routers.summaries.send_summary_email", fake)

    resp = await client.post(
        f"/api/summaries/{seed['summary_id']}/send",
        json={"contactIds": [seed["alice_id"]]},
        headers=other_auth,
    )
    assert resp.status_code == 404
    assert attempted == []
