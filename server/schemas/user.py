# TODO: Pydantic models for §Account.
# Expected:
#   - UserOut     ( id, email, fullName, role, hasCompletedSetup )
#   - UserUpdate  ( fullName?, email?, password? )
# Never expose password_hash.

from pydantic import BaseModel
