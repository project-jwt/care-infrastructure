# core/email.py — Resend client + send_summary_email for POST /api/summaries/:id/send
#
# Same shape as core/ai.py: configure the SDK once at import, expose one
# function, raise on failure and let the router translate that into a 502.
# The From address comes from EMAIL_SENDER (see config.py) — the default is
# Resend's sandbox address, which only delivers to our own account email;
# production overrides it with an address on the verified domain.

import asyncio
import html

import resend
from resend.exceptions import ResendError

from config import settings

resend.api_key = settings.resend_api_key


class EmailSendError(Exception):
    """The email provider failed (API error, quota, network). The send route
    catches exactly this — anything else escaping this module is one of our
    bugs and should surface as a 500, not be logged as a Resend failure."""


async def send_summary_email(
    to_email: str, summary_text: str, from_name: str | None = None
) -> None:
    """Email one summary to one trusted contact. Raises EmailSendError on any
    Resend/network failure — the send route catches and 502s, recording nothing.

    The resend SDK is synchronous (blocking HTTP), so the call runs in a
    worker thread via asyncio.to_thread instead of blocking the event loop.
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

    params: resend.Emails.SendParams = {
        "from": settings.email_sender,
        "to": [to_email],
        "subject": f"{sender_label} shared a summary with you",
        "html": body,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except ResendError as exc:
        # The SDK funnels every failure mode here — API rejections and
        # network errors alike (its transport wraps those as HttpClientError).
        raise EmailSendError(str(exc)) from exc
