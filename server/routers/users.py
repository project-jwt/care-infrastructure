# routers/users.py — spec §Account: the /api/users/me endpoints.
#
# "me" = whoever the Bearer token says. There is no GET /users/:id in this API —
# nobody can read anyone else's account, so the route path doesn't even offer it.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password, verify_password
from dependencies.auth import get_current_user
from dependencies.db import get_db
from models import user_model
from models.user_model import User
from schemas.user import AccountDelete, SetupOut, UserOut, UserUpdate

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
    """PATCH /api/users/me  { fullName?, email?, password?, currentPassword? } -> 200 updated user."""
    # exclude_unset: only fields the client actually sent — so PATCHing just
    # fullName doesn't stomp email with None.
    fields = body.model_dump(exclude_unset=True)

    # currentPassword isn't a column — pull it out before it reaches the model.
    current_password = fields.pop("current_password", None)

    # Step-up re-auth: changing the credentials that let you take over an
    # account (email, password) requires re-entering the current password, so
    # a valid token alone can't do it on a shared/unlocked device. Editing
    # only fullName stays token-only. Mirrors the delete flow's guard.
    if "email" in fields or "password" in fields:
        if current_password is None or not verify_password(
            current_password, user.password_hash
        ):
            raise HTTPException(status_code=403, detail="Current password is incorrect")

    # Raw password -> hash at the boundary, same as register. The model only
    # ever sees password_hash.
    if "password" in fields:
        fields["password_hash"] = hash_password(fields.pop("password"))

    # Changing email? Enforce uniqueness with a friendly 409 up front rather
    # than letting the DB's UNIQUE constraint blow up as a 500.
    if "email" in fields and fields["email"] != user.email:
        if await user_model.find_by_email(session, fields["email"]):
            raise HTTPException(status_code=409, detail="Email already registered")

    try:
        return await user_model.update(session, user.id, **fields)
    except IntegrityError:
        # Race: the email check above can pass while a concurrent request takes
        # the address; the UNIQUE constraint catches it — same 409.
        raise HTTPException(status_code=409, detail="Email already registered")


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


@router.delete("/me", status_code=204)
async def delete_me(
    body: AccountDelete,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """DELETE /api/users/me  { password } -> 204 No Content

    Irreversible. Three protections stack here:
      1. get_current_user proves WHO you are (401 without a valid token).
      2. The route is /me and only ever touches `user` — no id is accepted,
         so you can only delete your OWN account (no horizontal escalation).
      3. Step-up re-auth: the password is re-checked against the stored hash,
         so a valid token alone can't nuke the account (shared-device case).
    On success the DB's ON DELETE CASCADE removes the account's summaries,
    delivery records, and contact links along with the row.
    """
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect password")

    await user_model.delete(session, user.id)
    # 204: no body. The caller's token now references a gone account, so any
    # further request fails get_current_user's "User not found" 401.
    return None
