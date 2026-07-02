# TODO: Pydantic models for §Auth request/response bodies.
# Expected:
#   - RegisterIn  ( email, password, fullName, role )
#   - LoginIn     ( email, password )
#   - AuthOut     ( token, user: UserOut )
# Use alias_generator=to_camel + populate_by_name=True so JSON is camelCase.

from pydantic import BaseModel
