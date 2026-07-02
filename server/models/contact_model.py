# TODO: raw-SQL query functions for the trusted_contact_links table.
# Expected functions:
#   - list_by_owner(owner_id)                     # joins users to expose fullName/email
#   - create(owner_id, contact_id, nickname, relationship)
#   - find_by_link_id(link_id, owner_id)
#   - update(link_id, owner_id, **fields)
#   - delete(link_id, owner_id)
#   - is_contact_of(owner_id, contact_id)         # used when validating a /send payload

from db.pool import pool
