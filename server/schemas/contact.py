# TODO: Pydantic models for §Trusted Contacts.
# Expected:
#   - ContactCreate  ( contactEmail, nickname?, relationship? )
#   - ContactUpdate  ( nickname?, relationship? )
#   - ContactOut     ( linkId, contactId, fullName, email, nickname, relationship )

from pydantic import BaseModel
