# TODO: SQLAlchemy declarative model for the trusted_contact_links table plus
# async query helpers. Every helper takes an AsyncSession as its first arg.
# Expected helpers:
#   - list_by_owner(session, owner_id)                     # joins users to expose fullName/email
#   - create(session, owner_id, contact_id, nickname, relationship)
#   - find_by_link_id(session, link_id, owner_id)
#   - update(session, link_id, owner_id, **fields)
#   - delete(session, link_id, owner_id)
#   - is_contact_of(session, owner_id, contact_id)         # used when validating a /send payload

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from db.base import Base
