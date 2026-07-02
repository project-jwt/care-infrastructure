# TODO: raw-SQL query functions for the users table (spec §Schema Design).
# Expected functions:
#   - find(user_id)
#   - find_by_email(email)
#   - create(email, password_hash, full_name, role)
#   - update(user_id, **fields)
#   - validate_password(email, password)
#   - mark_setup_complete(user_id)
# Never return password_hash to callers.

from db.pool import pool
