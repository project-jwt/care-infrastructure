# TODO: FastAPI dependencies for JWT auth.
# Expected:
#   - get_current_user     -> parses Authorization: Bearer, decodes JWT, loads user, raises 401 on failure
#   - require_primary      -> get_current_user + assert role == 'primary', else 403
#   - require_contact      -> get_current_user + assert role == 'contact', else 403

from fastapi import Depends, HTTPException
