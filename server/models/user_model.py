# TODO: SQLAlchemy declarative model for the users table (spec §Schema Design) plus
# async query helpers. Every helper takes an AsyncSession as its first arg.
# Expected helpers:
#   - find(session, user_id)
#   - find_by_email(session, email)
#   - create(session, email, password_hash, full_name, role)
#   - update(session, user_id, **fields)
#   - validate_password(session, email, password)
#   - mark_setup_complete(session, user_id)
# Never return password_hash to callers.

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from db.base import Base
