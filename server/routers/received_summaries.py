# routers/received_summaries.py — spec §Contact Dashboard (Contact only)
#
# The read side of the send feature: everything primaries have shared WITH
# the current contact, newest send first. Contacts never edit or delete what
# was shared with them — the only writes here are none. They CAN view the
# photos attached to a summary sent to them, via the /raw endpoint below.

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import require_contact
from dependencies.db import get_db
from models import summary_model
from models.user_model import User
from schemas.summary import ImageOut, ReceivedSummaryOut, SummarySender

router = APIRouter(prefix="/received-summaries", tags=["received-summaries"])


@router.get("", response_model=list[ReceivedSummaryOut])
async def list_received_summaries(
    user: User = Depends(require_contact),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/received-summaries
    -> [ { summaryId, summaryText, sentAt, from: {...}, images: [...] }, ... ]

    require_contact mirrors the summaries router's require_primary: a
    primary-role token gets 403. The model helper is scoped by contact_id,
    so the list only ever contains rows addressed to the caller. Image
    metadata for every returned summary is loaded in ONE grouped query (no
    N+1); the bytes come from the /raw endpoint below.
    """
    rows = await summary_model.list_received_for_contact(session, user.id)
    images_by_summary = await summary_model.list_images_for_summaries(
        session, [row.summary_id for row in rows]
    )
    return [
        ReceivedSummaryOut(
            summary_id=row.summary_id,
            summary_text=row.summary_text,
            sent_at=row.sent_at,
            from_=SummarySender(id=row.sender_id, full_name=row.sender_name),
            images=[
                ImageOut(
                    id=img.id,
                    filename=img.filename,
                    content_type=img.content_type,
                    byte_size=img.byte_size,
                    created_at=img.created_at,
                )
                for img in images_by_summary.get(row.summary_id, [])
            ],
        )
        for row in rows
    ]


@router.get("/{summary_id}/images/{image_id}/raw")
async def get_received_summary_image_raw(
    summary_id: int,
    image_id: int,
    user: User = Depends(require_contact),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/received-summaries/:id/images/:imageId/raw -> the image bytes.

    Authorized ONLY if the summary was actually sent to this contact (a
    summary_recipients row links the two) — the same scoping the inbox list
    uses. A contact who wasn't a recipient gets 404, never another user's
    photo. nosniff + the stored content-type keep the browser from sniffing
    the bytes into executable HTML.
    """
    if not await summary_model.is_recipient(session, summary_id, user.id):
        raise HTTPException(status_code=404, detail="Image not found")
    img = await summary_model.find_image(session, summary_id, image_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=img.data,
        media_type=img.content_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )
