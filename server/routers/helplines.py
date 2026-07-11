# routers/helplines.py — spec §Helplines: the pre-loaded numbers a user can
# call for scam help (MVP §4).
#
# One read-only endpoint. Auth required (401 without a token) but NO role
# gate — the spec puts helplines behind login only, and a contact tapping a
# helpline is as legitimate as a primary.

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db
from models import helpline_model
from models.user_model import User
from schemas.helpline import HelplineOut

router = APIRouter(prefix="/helplines", tags=["helplines"])


@router.get("", response_model=list[HelplineOut])
async def list_helplines(
    user: User = Depends(get_current_user),  # auth gate only — value unused
    session: AsyncSession = Depends(get_db),
):
    """GET /api/helplines -> 200 [ { id, name, phone, hours, description } ]"""
    return await helpline_model.list_all(session)
