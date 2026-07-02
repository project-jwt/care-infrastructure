# TODO: raw-SQL query functions for the summaries and summary_recipients tables.
# Expected functions:
#   - create(user_id, transcript, summary_text)
#   - list_by_user(user_id)
#   - find_by_id(summary_id, user_id)         # scoped: returns None if not owned
#   - update_text(summary_id, user_id, summary_text)
#   - delete(summary_id, user_id)
#   - record_send(summary_id, contact_ids)    # inserts summary_recipients rows
#   - list_received_for_contact(contact_id)   # joins summaries + summary_recipients

from db.pool import pool
