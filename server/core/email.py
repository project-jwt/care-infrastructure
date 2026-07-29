# core/email.py — Resend client + the app's outbound email
#
# Three things live here:
#   send_summary_email        -> POST /api/summaries/:id/send
#   invite_signup_url         -> builds the link an invitation email carries
#   send_contact_invite_email -> POST /api/contacts, unregistered-email branch
#
# Same shape as core/ai.py: configure the SDK once at import, raise on failure
# and let the router translate that into a 502.
# The sender address comes from settings.email_sender: in production it's an
# address at our Resend-verified domain (projectjwt.marcylab.us); locally it
# falls back to Resend's sandbox sender.

import asyncio
import html
from urllib.parse import quote

import resend
from resend.exceptions import ResendError

from config import settings

resend.api_key = settings.resend_api_key

SENDER = settings.email_sender


class EmailSendError(Exception):
    """The email provider failed (API error, quota, network). The send route
    catches exactly this — anything else escaping this module is one of our
    bugs and should surface as a 500, not be logged as a Resend failure."""


async def send_summary_email(
    to_email: str,
    summary_text: str,
    from_name: str | None = None,
    attachments: list[dict] | None = None,
) -> None:
    """Email one summary to one trusted contact. Raises EmailSendError on any
    Resend/network failure — the send route catches and 502s, recording nothing.

    attachments (optional): the summary's photos, each a dict
    { filename, content (bytes), content_type }. They ride along as real email
    attachments; the body notes how many there are.

    The resend SDK is synchronous (blocking HTTP), so the call runs in a
    worker thread via asyncio.to_thread instead of blocking the event loop.
    """
    sender_label = from_name or "Someone you trust"
    attachments = attachments or []

    # summary_text is user content going into an HTML email: escape it, then
    # turn the draft's blank-line paragraph breaks into <p> blocks and the
    # single line breaks inside a paragraph into <br> (review: a med list
    # typed on three lines arrived as one run-on line).
    paragraphs = "".join(
        "<p>" + html.escape(part).replace("\n", "<br>") + "</p>"
        for part in summary_text.split("\n\n")
        if part.strip()
    )
    body = (
        f"<p>{html.escape(sender_label)} shared this summary with you:</p>"
        f"<blockquote>{paragraphs}</blockquote>"
    )
    if attachments:
        count = len(attachments)
        body += f"<p>{count} photo{'s' if count != 1 else ''} attached.</p>"

    params: resend.Emails.SendParams = {
        "from": SENDER,
        "to": [to_email],
        "subject": f"{sender_label} shared a summary with you",
        "html": body,
    }
    if attachments:
        # Resend's Attachment.content takes a list of byte-values (or base64);
        # list(bytes) gives exactly that, no encoding step.
        params["attachments"] = [
            {
                "filename": a.get("filename") or "photo",
                "content": list(a["content"]),
                "content_type": a["content_type"],
            }
            for a in attachments
        ]
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except ResendError as exc:
        # The SDK funnels every failure mode here — API rejections and
        # network errors alike (its transport wraps those as HttpClientError).
        raise EmailSendError(str(exc)) from exc


def invite_signup_url(email: str) -> str:
    """The link in an invite email: the SPA root with query params App.jsx
    reads on mount.

    Query params on "/" rather than a path like /register because the frontend
    has NO router — views are useState — so any other path would fall through
    to main.py's static catch-all and land the invitee on the home screen with
    no prefill.
    """
    base = settings.app_base_url.rstrip("/")
    return f"{base}/?invite=contact&email={quote(email)}"


async def send_contact_invite_email(
    to_email: str, from_name: str | None, signup_url: str
) -> None:
    """Ask an unregistered person to create a trusted-contact account.

    Deliberately carries NO summary content: this fires when a primary ADDS
    them, which is before any summary exists. Raises EmailSendError on any
    Resend/network failure, exactly like send_summary_email — the add route
    catches it and 502s, recording no invite.
    """
    inviter = from_name or "Someone"
    # inviter goes into HTML, so escape it (same rule as summary_text above).
    # The subject is not HTML and takes the raw value.
    safe_inviter = html.escape(inviter)
    body = (
        f"<p>{safe_inviter} would like to share health summaries with you "
        f"on J.W.T.</p>"
        f"<p>A trusted contact receives short written updates about how "
        f"someone is doing. To start receiving them, create a free trusted "
        f"contact account:</p>"
        f'<p><a href="{html.escape(signup_url, quote=True)}">'
        f"Create my trusted contact account</a></p>"
        f"<p>If you weren&rsquo;t expecting this, you can ignore this email.</p>"
    )

    params: resend.Emails.SendParams = {
        "from": SENDER,
        "to": [to_email],
        "subject": f"{inviter} would like to share health summaries with you",
        "html": body,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except ResendError as exc:
        raise EmailSendError(str(exc)) from exc
