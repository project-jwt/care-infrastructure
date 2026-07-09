# routers/summaries.py — spec §Summaries (Primary only)
#
# TODO (needs trusted contacts + core/email first):
#   - POST   /api/summaries/:id/send    -> email to trusted contacts, record sends
#
# ROUTE ORDER MATTERS: /draft is declared before /{summary_id}. FastAPI matches
# top-to-bottom, so a literal path like "draft" must come before a catch-all
# path parameter — otherwise POST /summaries/draft would try (and fail) to
# parse "draft" as the int summary_id.

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import draft_summary
from dependencies.auth import require_primary
from dependencies.db import get_db
from models import summary_model
from models.user_model import User
from schemas.summary import (
    DraftIn,
    DraftOut,
    SummaryCreate,
    SummaryListOut,
    SummaryOut,
    SummaryUpdate,
)

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
