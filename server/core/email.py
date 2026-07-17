# core/email.py — Gmail SMTP transport + send_summary_email for POST /api/summaries/:id/send
#
# Same shape as core/ai.py: expose one function, raise on failure and let the
# router translate that into a 502. The transport is stdlib smtplib against
# smtp.gmail.com — a dedicated Gmail account for the app plus an app password
# (see .env.example). No sandbox: any recipient works, ~500 sends/day cap.

import asyncio
import html
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from config import settings

# Gmail's implicit-TLS port. Gmail also rewrites any From that isn't the
# authenticated account, so the app's identity lives in the display name and
# the address is always the account we log in as.
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_NAME = "J.W.T"


class EmailSendError(Exception):
    """The email provider failed (auth rejection, quota, network). The send
    route catches exactly this — anything else escaping this module is one of
    our bugs and should surface as a 500, not be logged as a provider failure."""


def _send_blocking(msg: EmailMessage) -> None:
    """One connection per message: connect, authenticate, send, close. The
    send loop tops out at a handful of contacts, so connection reuse isn't
    worth managing a long-lived session's failure modes."""
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.send_message(msg)


async def send_summary_email(
    to_email: str, summary_text: str, from_name: str | None = None
) -> None:
    """Email one summary to one trusted contact. Raises EmailSendError on any
    SMTP/network failure — the send route catches it per recipient and reports
    the contact in the response's `failed` list.

    smtplib is synchronous (blocking sockets), so the call runs in a worker
    thread via asyncio.to_thread instead of blocking the event loop.
    """
    sender_label = from_name or "Someone you trust"

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

    msg = EmailMessage()
    msg["From"] = formataddr((SENDER_NAME, settings.gmail_address))
    msg["To"] = to_email
    msg["Subject"] = f"{sender_label} shared a summary with you"
    # Plain-text part first (the fallback for text-only clients), then the
    # HTML alternative — EmailMessage builds the multipart/alternative for us.
    msg.set_content(f"{sender_label} shared this summary with you:\n\n{summary_text}")
    msg.add_alternative(body, subtype="html")

    try:
        await asyncio.to_thread(_send_blocking, msg)
    except (smtplib.SMTPException, OSError) as exc:
        # SMTPException covers Gmail's rejections (bad app password, quota,
        # refused recipient); OSError covers the network layer (DNS, refused
        # connection, timeout). Both are provider-side — wrap and let the
        # router decide what a failed recipient means.
        raise EmailSendError(str(exc)) from exc
