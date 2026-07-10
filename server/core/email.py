# core/email.py — Resend client + send_summary_email for POST /api/summaries/:id/send
#
# Same shape as core/ai.py: configure the SDK once at import, expose one
# function, raise on failure and let the router translate that into a 502.
# Sender stays onboarding@resend.dev (Resend's sandbox address) until a real
# domain is verified.

import asyncio
import html

import resend

from config import settings

resend.api_key = settings.resend_api_key

SENDER = "J.W.T <onboarding@resend.dev>"


async def send_summary_email(
    to_email: str, summary_text: str, from_name: str | None = None
) -> None:
    """Email one summary to one trusted contact. Raises on any Resend/network
    failure — the send route catches and 502s, recording nothing.

    The resend SDK is synchronous (blocking HTTP), so the call runs in a
    worker thread via asyncio.to_thread instead of blocking the event loop.
    """
    sender_label = from_name or "Someone you trust"

    # summary_text is user content going into an HTML email: escape it, then
    # turn the draft's blank-line paragraph breaks into <p> blocks.
    paragraphs = "".join(
        f"<p>{html.escape(part)}</p>"
        for part in summary_text.split("\n\n")
        if part.strip()
    )
    body = (
        f"<p>{html.escape(sender_label)} shared this summary with you:</p>"
        f"<blockquote>{paragraphs}</blockquote>"
    )

    params: resend.Emails.SendParams = {
        "from": SENDER,
        "to": [to_email],
        "subject": f"{sender_label} shared a summary with you",
        "html": body,
    }
    await asyncio.to_thread(resend.Emails.send, params)
