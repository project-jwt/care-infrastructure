# routers/received_summaries.py — spec §Contact Dashboard (Contact only)
#
# The read side of the send feature: everything primaries have shared WITH
# the current contact, newest send first. One endpoint, read-only — contacts
# never edit or delete what was shared with them.

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import require_contact
from dependencies.db import get_db
from models import summary_model
from models.user_model import User
from schemas.summary import ReceivedSummaryOut, SummarySender

router = APIRouter(prefix="/received-summaries", tags=["received-summaries"])


@router.get("", response_model=list[ReceivedSummaryOut])
async def list_received_summaries(
    user: User = Depends(require_contact),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/received-summaries
    -> [ { summaryId, summaryText, sentAt, from: { id, fullName } }, ... ]

    require_contact mirrors the summaries router's require_primary: a
    primary-role token gets 403. The model helper is scoped by contact_id,
    so the list only ever contains rows addressed to the caller.
    """
    rows = await summary_model.list_received_for_contact(session, user.id)
    return [
        ReceivedSummaryOut(
            summary_id=row.summary_id,
            summary_text=row.summary_text,
            sent_at=row.sent_at,
            from_=SummarySender(id=row.sender_id, full_name=row.sender_name),
        )
        for row in rows
    ]
