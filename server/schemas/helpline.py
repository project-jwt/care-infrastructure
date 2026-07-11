# schemas/helpline.py — Pydantic models for spec §Helplines.

from schemas.base import CamelModel


class HelplineOut(CamelModel):
    """GET /api/helplines item: { id, name, phone, hours, description }.

    All field names are single words, so the camelCase aliasing is a no-op —
    CamelModel still buys from_attributes (serialize straight off the ORM row).
    """

    id: int
    name: str
    phone: str
    hours: str | None
    description: str | None
