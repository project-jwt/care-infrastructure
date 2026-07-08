# routers/summaries.py — spec §Summaries (Primary only)
#
# TODO (needs the summaries table / summary_model first):
#   - POST   /api/summaries             -> save a finalized summary
#   - GET    /api/summaries             -> list current user's summaries, newest first
#   - GET    /api/summaries/:id         -> one summary owned by current user
#   - PATCH  /api/summaries/:id         -> edit summaryText
#   - DELETE /api/summaries/:id         -> delete
#   - POST   /api/summaries/:id/send    -> email to trusted contacts, record sends

import logging

from fastapi import APIRouter, Depends, HTTPException

from core.ai import draft_summary
from dependencies.auth import require_primary
from models.user_model import User
from schemas.summary import DraftIn, DraftOut

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
        logger.exception("draft_summary failed")
        raise HTTPException(status_code=502, detail="Could not generate a summary right now — please try again")
