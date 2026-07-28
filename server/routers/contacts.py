# routers/contacts.py — spec §Trusted Contacts (Primary only)
#
# Adding a contact is BY EMAIL. If the email has a Contact account we link the
# two immediately; if it has NO account we send an invitation and hold a
# pending row until they register (models/invite_model.py).
#
# PRIVACY NOTE, now narrower than it was: "account exists but isn't a Contact"
# still returns 404 with the same string it always did, but an unregistered
# email now returns 201 "invited" instead of that 404 — so the two cases are
# distinguishable, and a caller can probe whether an email is registered. That
# is a deliberate, documented tradeoff (see the spec's "Accepted tradeoffs");
# the invite caps below bound how fast it can be exploited.

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.email import EmailSendError, invite_signup_url, send_contact_invite_email
from dependencies.auth import require_primary
from dependencies.db import get_db
from models import contact_model, invite_model, user_model
from models.user_model import User
from schemas.contact import ContactCreate, ContactOut, ContactUpdate, InviteUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["contacts"])

# Invite caps. This endpoint sends email to addresses nobody has verified, so
# these bound the damage if an account is abused. Counted with plain queries —
# no rate-limit middleware in this app.
MAX_OPEN_INVITES = 10          # invitations one primary may have waiting
MAX_INVITES_PER_DAY = 10       # new invitations per rolling window, below
INVITE_WINDOW = timedelta(hours=24)
# Per-invite resend cooldown. NOTE this is not counted against the daily cap,
# so the honest worst case for one primary is MAX_OPEN_INVITES * 24 resends a
# day; raising this to 24h is the one-line fix if that proves too loose.
RESEND_COOLDOWN = timedelta(hours=1)


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


async def _send_invite(owner: User, email: str) -> None:
    """Email an invitation, translating a provider failure into a 502 the same
    way the summary-send route does — so the caller records nothing."""
    try:
        await send_contact_invite_email(email, owner.full_name, invite_signup_url(email))
    except EmailSendError:
        # Resend outage/quota/network. Log the real error, send a generic 502;
        # a bug of ours propagates as a 500 rather than masquerading as this.
        logger.exception("send_contact_invite_email failed")
        raise HTTPException(
            status_code=502,
            detail="Could not send the invitation right now — please try again",
        )


async def _invite_unregistered(
    session: AsyncSession, owner: User, body: ContactCreate
) -> ContactOut:
    """The no-account-yet branch of POST /api/contacts.

    Order matches the summary-send route's rule — validate everything, then
    email, then record — so a rejected invite leaves no row behind and a
    provider outage leaves no half-state.
    """
    email = body.contact_email.lower()  # the model stores lowercased only

    # find_any, not find_pending: an ACCEPTED row still owns the UNIQUE
    # (owner_id, email), so we have to see it here to revive it below.
    existing = await invite_model.find_any(session, owner.id, email)
    if existing is not None and existing.accepted_at is None:
        raise HTTPException(
            status_code=409, detail="You've already invited this person"
        )

    if await invite_model.count_open(session, owner.id) >= MAX_OPEN_INVITES:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have {MAX_OPEN_INVITES} invitations still waiting. "
                "Cancel one before sending another."
            ),
        )
    cutoff = datetime.now(timezone.utc) - INVITE_WINDOW
    if await invite_model.count_recent(session, owner.id, cutoff) >= MAX_INVITES_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail="You've sent a lot of invitations today. Please try again tomorrow.",
        )

    await _send_invite(owner, email)  # email BEFORE recording

    if existing is not None:
        # Accepted row: re-open it rather than inserting a colliding second one.
        invite = await invite_model.revive(
            session, existing, body.nickname, body.relationship
        )
    else:
        try:
            invite = await invite_model.create(
                session, owner.id, email, body.nickname, body.relationship
            )
        except IntegrityError:
            # Race: two simultaneous adds both passed the check above. The
            # loser reports the same 409 as the checked case — the invitee got
            # one extra email, but there's no duplicate row. Same tradeoff
            # summary_model.record_send already accepts.
            raise HTTPException(
                status_code=409, detail="You've already invited this person"
            )
    return _invite_out(invite)


@router.post("", response_model=ContactOut, status_code=201)
async def add_contact(
    body: ContactCreate,
    user: User = Depends(require_primary),
    session: AsyncSession = Depends(get_db),
):
    """POST /api/contacts  { contactEmail, nickname?, relationship? } -> 201.

    Three outcomes:
      - a Contact account exists           -> link them, status "active"
      - no account at all                  -> invite them, status "invited"
      - an account exists, wrong role      -> 404 (see the privacy note up top)
    409 when this person is already on the list or already invited.
    """
    # Case-insensitive on purpose: the primary can't know how the contact
    # capitalized their email at registration (review: exact match made
    # legitimately-registered contacts un-addable).
    contact_user = await user_model.find_by_email_ci(session, body.contact_email)

    if contact_user is None:
        return await _invite_unregistered(session, user, body)

    if contact_user.role != "contact":
        # Exact spec string, unchanged. It deliberately doesn't say "contact" —
        # naming the role would leak more than the mere existence already does.
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
