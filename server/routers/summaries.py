# routers/summaries.py — spec §Summaries (Primary only)
#
# ROUTE ORDER MATTERS: /draft is declared before /{summary_id}. FastAPI matches
# top-to-bottom, so a literal path like "draft" must come before a catch-all
# path parameter — otherwise POST /summaries/draft would try (and fail) to
# parse "draft" as the int summary_id.

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import draft_summary
from core.email import EmailSendError, send_summary_email
from core.transcription import TranscriptionError, transcribe_audio
from dependencies.auth import require_primary
from dependencies.db import get_db
from models import contact_model, summary_model, user_model
from models.user_model import User
from schemas.summary import (
    DraftIn,
    DraftOut,
    RecipientOut,
    SendIn,
    SendOut,
    SentTo,
    SummaryCreate,
    SummaryListOut,
    SummaryOut,
    SummaryUpdate,
    TranscriptOut,
)

# Reject audio uploads larger than this before spending a transcription call.
# A spoken problem description is seconds long; anything much bigger is a
# mistake or abuse, not a real recording.
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/draft", response_model=DraftOut)
async def draft(body: DraftIn, user: User = Depends(require_primary)):
    """POST /api/summaries/draft  { transcript, answers=[] }
    -> { needsClarification: true, questions } or { needsClarification: false, summaryText }

    First use of require_primary: a Contact-role token gets 403 before this
    body runs (spec: Summaries are Primary only). Note there's no get_db —
    this endpoint is stateless and never touches the database.
    """
    try:
        return await draft_summary(body.transcript, body.answers)
    except Exception:
        # Gemini outage/quota/network — not the client's fault, and the raw
        # error may mention internals, so log it and send a generic 502.
        # TODO(post-MVP, review #6): catch only the genai SDK's exception
        # types here and let genuine bugs 500 through main.py's handlers,
        # instead of flattening everything into the same 502.
        logger.exception("draft_summary failed")
        raise HTTPException(status_code=502, detail="Could not generate a summary right now — please try again")


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    audio: UploadFile = File(...),
    user: User = Depends(require_primary),
):
    """POST /api/summaries/transcribe  (multipart form, field "audio") -> { transcript }

    For iOS / browsers without the Web Speech API: the frontend records the
    user speaking and uploads the clip here to be transcribed. Primary-only,
    like /draft — it's part of the same speak flow. Stateless, no DB.
    """
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        # 413 (not 502): the client sent too much — a real, actionable status.
        raise HTTPException(status_code=413, detail="That recording is too large.")
    try:
        transcript = await transcribe_audio(audio_bytes, audio.content_type or "")
        return TranscriptOut(transcript=transcript)
    except TranscriptionError:
        # No key, provider outage, or unusable audio — not the client's fault,
        # and the raw error may mention internals, so log it and send a generic
        # 502. The frontend falls back to letting the user type.
        logger.exception("transcribe_audio failed")
        raise HTTPException(status_code=502, detail="Could not turn your recording into words — please try again or type instead")


@router.post("", response_model=SummaryOut, status_code=201)
async def create_summary(
    body: SummaryCreate,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/summaries  { transcript?, summaryText } -> 201 saved summary.

    Called when the user approves the draft on the review screen. Ownership
    comes from the token (user.id), never from the request body — a client
    can't save a summary onto someone else's account.
    """
    return await summary_model.create(session, user.id, body.transcript, body.summary_text)


@router.get("", response_model=list[SummaryListOut])
async def list_summaries(
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/summaries -> the current user's summaries, newest first.
    response_model=list[...] runs every row through SummaryListOut — which has
    no transcript field, so the list stays light (spec's list shape)."""
    return await summary_model.list_by_user(session, user.id)


@router.get("/{summary_id}", response_model=SummaryOut)
async def get_summary(
    summary_id: int,  # path param: /api/summaries/7 -> summary_id=7; "/abc" -> 422
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/summaries/:id -> one summary, transcript included.
    404 for both "doesn't exist" and "not yours" — find_by_id is owner-scoped,
    so this route can't tell the difference, and neither can a snooper."""
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary


@router.get("/{summary_id}/recipients", response_model=list[RecipientOut])
async def list_summary_recipients(
    summary_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/summaries/:id/recipients -> who this summary was sent to
    ({ contactId, fullName, sentAt }), oldest send first — the sender's receipt.

    Owner-scoped exactly like get_summary: find_by_id returns None for both
    "doesn't exist" and "not yours", so a primary can't read another primary's
    recipient list — 404 either way. An unsent summary returns []. A recipient
    who has deleted their account comes back with contactId/fullName null
    ("Deleted user")."""
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")

    rows = await summary_model.list_recipients_for_summary(session, summary_id)
    return [
        RecipientOut(
            contact_id=r.contact_id,
            nickname=r.nickname,
            full_name=r.full_name,
            sent_at=r.sent_at,
        )
        for r in rows
    ]


@router.patch("/{summary_id}", response_model=SummaryOut)
async def update_summary(
    summary_id: int,
    body: SummaryUpdate,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """PATCH /api/summaries/:id  { summaryText } -> updated summary
    (updated_at bumps automatically via the column's onupdate)."""
    summary = await summary_model.update_text(session, summary_id, user.id, body.summary_text)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary


@router.delete("/{summary_id}")
async def delete_summary(
    summary_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """DELETE /api/summaries/:id -> 200 { message } (spec's success shape)."""
    deleted = await summary_model.delete(session, summary_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"message": "Summary deleted"}


@router.post("/{summary_id}/send", response_model=SendOut)
async def send_summary(
    summary_id: int,
    body: SendIn,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/summaries/:id/send  { contactIds } -> { summaryId, sentTo }

    Order matters here — validate EVERYTHING, then email, then record:
      1. 404 unless the summary exists and is the caller's (owner-scoped).
      2. 403 if ANY contactId isn't on the caller's trusted list — checked
         before a single email goes out, so a bad id can't cause a partial send.
      3. Email every contact; any Resend failure -> 502 and, because
         record_send hasn't run yet, nothing lands in summary_recipients
         (acceptance criterion: failed sends record nothing).
    """
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")

    # Dedupe while keeping order — sending [3, 3] shouldn't email twice.
    contact_ids = list(dict.fromkeys(body.contact_ids))

    recipients = []
    for contact_id in contact_ids:
        if not await contact_model.is_contact_of(session, user.id, contact_id):
            raise HTTPException(
                status_code=403, detail="A contactId is not a trusted contact"
            )
        recipient = await user_model.find(session, contact_id)
        if recipient is None:
            # The trust check passed but the account vanished before this
            # read (deleted mid-send). Same 403 as an untrusted id — to the
            # caller the two cases are indistinguishable on purpose.
            raise HTTPException(
                status_code=403, detail="A contactId is not a trusted contact"
            )
        recipients.append(recipient)

    try:
        for recipient in recipients:
            await send_summary_email(
                recipient.email, summary.summary_text, from_name=user.full_name
            )
    except EmailSendError:
        # Resend outage/quota/network — same treatment as /draft's Gemini
        # failure: log the real error, send a generic 502, record nothing.
        # Only the provider's failures land here; a bug of ours propagates
        # as a 500 instead of masquerading as a Resend outage.
        logger.exception("send_summary_email failed")
        raise HTTPException(
            status_code=502,
            detail="Could not send the summary right now — please try again",
        )

    try:
        rows = await summary_model.record_send(session, summary_id, contact_ids)
    except IntegrityError:
        # Vanishingly narrow race: a contact account (or the summary) deleted
        # between validation above and this insert trips the FK. The emails
        # did go out; the honest answer is still "the send didn't complete" —
        # get_db rolls the failed transaction back on close.
        logger.exception("record_send hit an FK violation after emails were sent")
        raise HTTPException(
            status_code=502,
            detail="Could not send the summary right now — please try again",
        )
    return SendOut(
        summary_id=summary_id,
        sent_to=[SentTo(contact_id=row.contact_id, sent_at=row.sent_at) for row in rows],
    )
