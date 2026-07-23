# routers/summaries.py — spec §Summaries (Primary only)
#
# ROUTE ORDER MATTERS: /draft is declared before /{summary_id}. FastAPI matches
# top-to-bottom, so a literal path like "draft" must come before a catch-all
# path parameter — otherwise POST /summaries/draft would try (and fail) to
# parse "draft" as the int summary_id.

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
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
    ImageOut,
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

# Image attachment limits (spec): 2 photos per summary, 10 MB each, and only
# the three web-safe raster formats. The magic-byte prefixes below re-check the
# actual bytes so a client can't smuggle HTML/SVG in under a "image/png"
# content-type header (defence in depth alongside X-Content-Type-Options).
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_IMAGES_PER_SUMMARY = 2
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _sniff_image_type(data: bytes) -> str | None:
    """Return the content-type implied by the leading bytes, or None if the
    data isn't one of our allowed raster formats. Guards against a mislabelled
    or malicious upload (e.g. HTML/SVG claiming to be image/png)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None

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
        RecipientOut(contact_id=r.contact_id, full_name=r.full_name, sent_at=r.sent_at)
        for r in rows
    ]


# ── Image attachments (primary manages their own summary's photos) ────────────
# Every endpoint resolves the summary through the owner-scoped find_by_id first,
# so another primary's summary is a 404 (never "403" — we don't confirm it
# exists), the same rule as the rest of this router.


def _image_out(row) -> ImageOut:
    return ImageOut(
        id=row.id,
        filename=row.filename,
        content_type=row.content_type,
        byte_size=row.byte_size,
        created_at=row.created_at,
    )


@router.get("/{summary_id}/images", response_model=list[ImageOut])
async def list_summary_images(
    summary_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/summaries/:id/images -> the summary's photos as metadata
    (no bytes), oldest first."""
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    rows = await summary_model.list_images(session, summary_id)
    return [_image_out(r) for r in rows]


@router.post("/{summary_id}/images", response_model=ImageOut, status_code=201)
async def upload_summary_image(
    summary_id: int,
    image: UploadFile = File(...),
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/summaries/:id/images  (multipart form, field "image") -> ImageOut

    Rejections: 404 not the caller's summary; 415 wrong type (by header AND by
    magic bytes); 413 over 10 MB; 409 the summary already has 2 photos.
    """
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="That file type isn't supported. Please use a JPEG, PNG, or WebP image.",
        )

    # Read at most MAX+1 bytes so a huge upload can't balloon memory before the
    # size check — len > MAX means it overflowed the cap.
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="That image is too large. Please use one under 10 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="That image was empty.")

    # The header said an allowed type; confirm the bytes actually are one, and
    # that they match the claim — blocks a mislabelled/polyglot upload.
    sniffed = _sniff_image_type(data)
    if sniffed is None or sniffed != image.content_type:
        raise HTTPException(
            status_code=415,
            detail="That file didn't look like a JPEG, PNG, or WebP image.",
        )

    # Cap check LAST, just before the insert, to keep the window small. Two
    # truly-simultaneous uploads could still both pass — acceptable for a
    # single-user flow; the DB is not the enforcement point for "at most 2".
    if await summary_model.count_images(session, summary_id) >= MAX_IMAGES_PER_SUMMARY:
        raise HTTPException(
            status_code=409,
            detail=f"A summary can have at most {MAX_IMAGES_PER_SUMMARY} photos. Remove one first.",
        )

    img = await summary_model.add_image(
        session,
        summary_id,
        content_type=image.content_type,
        filename=image.filename,
        byte_size=len(data),
        data=data,
    )
    return _image_out(img)


@router.get("/{summary_id}/images/{image_id}/raw")
async def get_summary_image_raw(
    summary_id: int,
    image_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/summaries/:id/images/:imageId/raw -> the image bytes.

    nosniff + the stored content-type mean the browser treats the response as
    exactly that image and never sniffs it into executable HTML."""
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    img = await summary_model.find_image(session, summary_id, image_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=img.data,
        media_type=img.content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{summary_id}/images/{image_id}", status_code=204)
async def delete_summary_image(
    summary_id: int,
    image_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """DELETE /api/summaries/:id/images/:imageId -> 204. 404 if the image isn't
    on a summary the caller owns."""
    summary = await summary_model.find_by_id(session, summary_id, user.id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    if not await summary_model.delete_image(session, summary_id, image_id):
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(status_code=204)


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

    # Load the summary's photos once (after validation, before the email loop)
    # and attach the same set to every recipient's email.
    images = await summary_model.load_images_with_data(session, summary_id)
    attachments = [
        {"filename": img.filename, "content": img.data, "content_type": img.content_type}
        for img in images
    ]

    try:
        for recipient in recipients:
            await send_summary_email(
                recipient.email,
                summary.summary_text,
                from_name=user.full_name,
                attachments=attachments,
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
