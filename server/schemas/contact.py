# schemas/contact.py — request/response shapes for §Trusted Contacts
# (Primary only).

from pydantic import EmailStr

from schemas.base import CamelModel


class ContactCreate(CamelModel):
    """POST /api/contacts body: { contactEmail, nickname?, relationship? }
    The contact must already have a Contact account — the router looks the
    email up and 404s if there's no matching contact account."""

    contact_email: EmailStr
    nickname: str | None = None
    relationship: str | None = None


class ContactUpdate(CamelModel):
    """PATCH /api/contacts/:linkId body: { nickname?, relationship? }
    Both optional — only the fields actually sent get updated (the router
    uses exclude_unset to tell "omitted" apart from "set to null")."""

    nickname: str | None = None
    relationship: str | None = None


class ContactOut(CamelModel):
    """Response shape for every contacts endpoint that returns a link:
    { linkId, contactId, fullName, email, nickname, relationship }
    linkId/nickname/relationship come from the link row; contactId/fullName/
    email from the joined users row — the router composes the two."""

    link_id: int
    contact_id: int
    full_name: str
    email: str
    nickname: str | None
    relationship: str | None
