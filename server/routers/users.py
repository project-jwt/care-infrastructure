# routers/users.py — spec §Account: the /api/users/me endpoints.
#
# "me" = whoever the Bearer token says. There is no GET /users/:id in this API —
# nobody can read anyone else's account, so the route path doesn't even offer it.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from dependencies.auth import get_current_user
from dependencies.db import get_db
from models import user_model
from models.user_model import User
from schemas.user import SetupOut, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    """GET /api/users/me -> 200 the current user.

    The whole handler is `return user`: get_current_user already decoded the
    token and loaded the row, and response_model=UserOut drops password_hash.
    """
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),  # same session get_current_user used (per-request cache)
):
    """PATCH /api/users/me  { fullName?, email?, password? } -> 200 updated user."""
    # exclude_unset: only fields the client actually sent — so PATCHing just
    # fullName doesn't stomp email with None.
    fields = body.model_dump(exclude_unset=True)

    # Raw password -> hash at the boundary, same as register. The model only
    # ever sees password_hash.
    if "password" in fields:
        fields["password_hash"] = hash_password(fields.pop("password"))

    # Changing email? Enforce uniqueness with a friendly 409 up front rather
    # than letting the DB's UNIQUE constraint blow up as a 500.
    if "email" in fields and fields["email"] != user.email:
        if await user_model.find_by_email(session, fields["email"]):
            raise HTTPException(status_code=409, detail="Email already registered")

    return await user_model.update(session, user.id, **fields)


@router.patch("/me/setup", response_model=SetupOut)
async def complete_setup(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """PATCH /api/users/me/setup -> 200 { id, hasCompletedSetup }

    No body: the endpoint's only job is flipping the flag to true after the
    onboarding tutorial (spec MVP story 6).
    """
    return await user_model.mark_setup_complete(session, user.id)
