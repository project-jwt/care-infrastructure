# tests/test_contact_invites.py — trusted-contact invitations:
#   - the contact_invites table and its helpers (model layer)
#   - POST /api/contacts inviting an unregistered email
#   - the invite endpoints (patch / resend / cancel)
#   - acceptance: registering as a contact converts pending invites into links

from datetime import datetime, timedelta, timezone

from core.security import create_access_token
from models import contact_model, invite_model
from models.invite_model import ContactInvite
from models.user_model import User


async def _user(session, *, email, full_name="U", role="primary"):
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ── model layer ───────────────────────────────────────────────────────────────


async def test_create_then_find_and_list_pending(session):
    owner = await _user(session, email="p@example.com")
    await session.commit()

    invite = await invite_model.create(
        session, owner.id, "new@example.com", "Mom", "mother"
    )
    assert invite.id is not None
    assert invite.accepted_at is None
    assert invite.created_at is not None
    assert invite.last_sent_at is not None

    found = await invite_model.find_any(session, owner.id, "new@example.com")
    assert found is not None and found.id == invite.id

    pending = await invite_model.list_pending_by_owner(session, owner.id)
    assert [i.id for i in pending] == [invite.id]


async def test_find_any_is_owner_scoped(session):
    a = await _user(session, email="a@example.com")
    b = await _user(session, email="b@example.com")
    await session.commit()

    await invite_model.create(session, a.id, "x@example.com", None, None)

    # b invited nobody — a's invite must be invisible to them.
    assert await invite_model.find_any(session, b.id, "x@example.com") is None


async def test_accepted_invites_are_excluded_from_pending_but_still_found(session):
    owner = await _user(session, email="p2@example.com")
    await session.commit()

    invite = await invite_model.create(session, owner.id, "acc@example.com", None, None)
    invite.accepted_at = datetime.now(timezone.utc)
    await session.commit()

    assert await invite_model.list_pending_by_owner(session, owner.id) == []
    # find_any still sees it — that's what makes revive possible.
    assert await invite_model.find_any(session, owner.id, "acc@example.com") is not None


async def test_revive_clears_acceptance_and_rewrites_labels(session):
    owner = await _user(session, email="p3@example.com")
    await session.commit()

    invite = await invite_model.create(session, owner.id, "rev@example.com", "Old", "old")
    old_created = invite_model.as_utc(invite.created_at)
    invite.accepted_at = datetime.now(timezone.utc)
    await session.commit()

    revived = await invite_model.revive(session, invite, "New", "new")
    assert revived.accepted_at is None
    assert revived.nickname == "New"
    assert revived.relationship == "new"
    assert invite_model.as_utc(revived.created_at) >= old_created


async def test_count_open_and_count_recent(session):
    owner = await _user(session, email="p4@example.com")
    await session.commit()

    await invite_model.create(session, owner.id, "one@example.com", None, None)
    old = await invite_model.create(session, owner.id, "two@example.com", None, None)

    # Backdate one invite past the 24h window, and accept it so it stops
    # counting as open — count_recent must still ignore the window, not the
    # acceptance.
    old.created_at = datetime.now(timezone.utc) - timedelta(hours=30)
    old.accepted_at = datetime.now(timezone.utc)
    await session.commit()

    assert await invite_model.count_open(session, owner.id) == 1
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    assert await invite_model.count_recent(session, owner.id, cutoff) == 1


async def test_delete_pending_is_owner_scoped(session):
    a = await _user(session, email="da@example.com")
    b = await _user(session, email="db@example.com")
    await session.commit()

    invite = await invite_model.create(session, a.id, "z@example.com", None, None)

    assert await invite_model.delete_pending(session, invite.id, b.id) is False
    assert await invite_model.delete_pending(session, invite.id, a.id) is True
    assert await invite_model.find_any(session, a.id, "z@example.com") is None


async def test_accept_for_user_creates_links_for_every_inviter(session):
    a = await _user(session, email="ia@example.com")
    b = await _user(session, email="ib@example.com")
    await session.commit()

    await invite_model.create(session, a.id, "joins@example.com", "Kid", "son")
    await invite_model.create(session, b.id, "joins@example.com", None, None)
    await session.commit()

    contact = await _user(session, email="joins@example.com", role="contact")
    await session.commit()

    accepted = await invite_model.accept_for_user(session, contact)
    assert accepted == 2
    assert await contact_model.is_contact_of(session, a.id, contact.id) is True
    assert await contact_model.is_contact_of(session, b.id, contact.id) is True

    # Labels carry across from the invite onto the link.
    links = await contact_model.list_by_owner(session, a.id)
    assert [(l.nickname, l.relationship) for l, _ in links] == [("Kid", "son")]

    # And nothing is left pending.
    assert await invite_model.list_pending_by_owner(session, a.id) == []


async def test_accept_for_user_matches_email_case_insensitively(session):
    owner = await _user(session, email="ci@example.com")
    await session.commit()
    await invite_model.create(session, owner.id, "mixed@example.com", None, None)
    await session.commit()

    contact = await _user(session, email="MiXeD@example.com", role="contact")
    await session.commit()

    assert await invite_model.accept_for_user(session, contact) == 1


async def test_accept_for_user_skips_an_existing_link(session):
    """They were linked, deleted their account, re-registered while an invite
    was still pending — the link INSERT must be skipped, not raise."""
    owner = await _user(session, email="dup@example.com")
    contact = await _user(session, email="already@example.com", role="contact")
    await session.commit()

    await contact_model.create(session, owner.id, contact.id, None, None)
    await invite_model.create(session, owner.id, "already@example.com", None, None)
    await session.commit()

    assert await invite_model.accept_for_user(session, contact) == 1
    links = await contact_model.list_by_owner(session, owner.id)
    assert len(links) == 1  # not two
