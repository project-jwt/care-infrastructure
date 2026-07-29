# tests/test_primary_invites.py — the REVERSE invitation direction: a trusted
# contact invites someone to create a primary account and add them.
#
# Two layers in one file, because the feature is one endpoint and one email:
#   - the email params and the signup link (no Resend calls; the SDK's send is
#     replaced with a recorder)
#   - POST /api/invitations/primary (role gate, 502, no-enumeration)

import pytest
import resend

from core.email import (
    EmailSendError,
    primary_signup_url,
    send_primary_invite_email,
)
from core.security import create_access_token
from models.user_model import User


async def _user(session, *, email, full_name="U", role="contact"):
    user = User(email=email, password_hash="x", full_name=full_name, role=role)
    session.add(user)
    await session.flush()
    return user


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def sent(monkeypatch):
    """Capture the params dict instead of calling Resend."""
    captured = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: captured.append(params))
    return captured


# ── the email + the link ──────────────────────────────────────────────────────


async def test_invite_names_the_contact_and_carries_their_address(sent):
    await send_primary_invite_email(
        "newprimary@example.com",
        from_name="Chris Hackett",
        from_email="chris@example.com",
        signup_url="http://x/?invite=primary&email=a%40b.com&contact=chris%40example.com",
    )
    assert len(sent) == 1
    params = sent[0]
    assert params["to"] == ["newprimary@example.com"]
    assert "Chris Hackett" in params["subject"]
    assert "Chris Hackett" in params["html"]
    # The whole mechanism: the primary needs this address to add them.
    assert "chris@example.com" in params["html"]
    # & in the href must be escaped for HTML, so the link survives intact.
    assert "&amp;contact=chris%40example.com" in params["html"]
    # Nothing has been shared yet, so there is no health content to leak.
    assert "attachments" not in params


async def test_invite_escapes_the_contacts_name_and_address(sent):
    await send_primary_invite_email(
        "a@example.com",
        from_name="<script>x</script>",
        from_email="<b>me</b>@example.com",
        signup_url="http://x/",
    )
    html = sent[0]["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>me</b>" not in html


async def test_invite_falls_back_when_the_contact_has_no_name(sent):
    await send_primary_invite_email(
        "a@example.com", from_name=None, from_email="c@example.com", signup_url="http://x/"
    )
    assert "Someone" in sent[0]["subject"]


async def test_invite_wraps_provider_failures(monkeypatch):
    def boom(params):
        raise resend.exceptions.ResendError(
            code=500, message="down", error_type="x", suggested_action="y"
        )

    monkeypatch.setattr(resend.Emails, "send", boom)
    with pytest.raises(EmailSendError):
        await send_primary_invite_email(
            "a@example.com", from_name="C", from_email="c@example.com", signup_url="http://x/"
        )


def test_signup_url_carries_both_addresses_encoded(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com/")
    url = primary_signup_url("new+user@example.com", "chris@example.com")
    assert url == (
        "https://app.example.com/?invite=primary"
        "&email=new%2Buser%40example.com"
        "&contact=chris%40example.com"
    )
