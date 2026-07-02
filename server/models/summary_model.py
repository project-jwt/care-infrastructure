# TODO: SQLAlchemy declarative models for the summaries and summary_recipients
# tables plus async query helpers. Every helper takes an AsyncSession as its first arg.
# Expected helpers:
#   - create(session, user_id, transcript, summary_text)
#   - list_by_user(session, user_id)
#   - find_by_id(session, summary_id, user_id)         # scoped: returns None if not owned
#   - update_text(session, summary_id, user_id, summary_text)
#   - delete(session, summary_id, user_id)
#   - record_send(session, summary_id, contact_ids)    # inserts summary_recipients rows
#   - list_received_for_contact(session, contact_id)   # joins summaries + summary_recipients

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from db.base import Base
