# routers/contacts.py — spec §Trusted Contacts (Primary only)
#
# Adding a contact is BY EMAIL, and the account must already exist with the
# Contact role (spec decision). Deliberate privacy rule: "no account with
# that email" and "account exists but isn't a Contact" return the IDENTICAL
# 404 — the API never reveals whether an email is registered or what role it
# holds. The frontend turns this into "ask them to sign up first".

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import require_primary
from dependencies.db import get_db
from models import contact_model, invite_model, user_model
from models.user_model import User
from schemas.contact import ContactCreate, ContactOut, ContactUpdate, InviteUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _to_out(link, contact_user) -> ContactOut:
    """Compose the contract's response shape from a (link, users) join pair."""
    return ContactOut(
        status="active",
        link_id=link.id,
        contact_id=contact_user.id,
        full_name=contact_user.full_name,
        email=contact_user.email,
        nickname=link.nickname,
        relationship=link.relationship,
    )


def _invite_out(invite) -> ContactOut:
    """The same response shape for a pending invitation. No contactId and no
    fullName exist yet — that's what status="invited" tells the client."""
    return ContactOut(
        status="invited",
        email=invite.email,
        nickname=invite.nickname,
        relationship=invite.relationship,
        invite_id=invite.id,
        invited_at=invite.created_at,
    )


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """GET /api/contacts -> the current primary user's trusted contacts,
    followed by the people they've invited who haven't registered yet.

    Active first on purpose: greyed-out invitations must never push usable
    contacts down the screen.
    """
    rows = await contact_model.list_by_owner(session, user.id)
    invites = await invite_model.list_pending_by_owner(session, user.id)
    return [_to_out(link, contact_user) for link, contact_user in rows] + [
        _invite_out(invite) for invite in invites
    ]


@router.post("", response_model=ContactOut, status_code=201)
async def add_contact(
    body: ContactCreate,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/contacts  { contactEmail, nickname?, relationship? } -> 201 link.

    404 when the email has no CONTACT account (see privacy note up top),
    409 when this contact is already on the list.
    """
    # Case-insensitive on purpose: the primary can't know how the contact
    # capitalized their email at registration (review: exact match made
    # legitimately-registered contacts un-addable).
    contact_user = await user_model.find_by_email_ci(session, body.contact_email)
    if contact_user is None or contact_user.role != "contact":
        # Exact spec string — the frontend matches on it, and it deliberately
        # doesn't say "contact" (the privacy note up top: never reveal whether
        # the email exists or what role it holds).
        raise HTTPException(status_code=404, detail="No account with that email")

    if await contact_model.is_contact_of(session, user.id, contact_user.id):
        raise HTTPException(status_code=409, detail="Contact already added")

    try:
        link = await contact_model.create(
            session, user.id, contact_user.id, body.nickname, body.relationship
        )
    except IntegrityError:
        # Race: two simultaneous adds can both pass the check above; the
        # UNIQUE (owner_id, contact_id) catches the loser — same 409.
        # NOTE this catch is broader than that one constraint: the two FKs
        # land here too. Unreachable today (no user-deletion endpoint), but
        # if accounts become deletable, a contact vanishing mid-request would
        # read as "already added" — split the handling then.
        raise HTTPException(status_code=409, detail="Contact already added")
    return _to_out(link, contact_user)


@router.patch("/{link_id}", response_model=ContactOut)
async def update_contact(
    link_id: int,
    body: ContactUpdate,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """PATCH /api/contacts/:linkId  { nickname?, relationship? } -> updated link.

    exclude_unset: only fields the client actually sent get updated, so
    omitting nickname is different from sending nickname: null.
    """
    fields = body.model_dump(exclude_unset=True)
    row = await contact_model.update(session, link_id, user.id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _to_out(*row)


@router.delete("/{link_id}")
async def delete_contact(
    link_id: int,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """DELETE /api/contacts/:linkId -> 200 { message } (spec's success shape).
    404 for both "doesn't exist" and "not yours" — delete is owner-scoped."""
    deleted = await contact_model.delete(session, link_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact removed"}
