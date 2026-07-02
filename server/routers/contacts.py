# TODO: implement per spec §Trusted Contacts
#   - GET    /api/contacts             -> list current primary user's trusted contacts
#   - POST   /api/contacts             -> add by contactEmail (contact account must exist)
#   - PATCH  /api/contacts/:linkId     -> edit nickname / relationship
#   - DELETE /api/contacts/:linkId     -> remove link

from fastapi import APIRouter

# router = APIRouter(prefix="/contacts", tags=["contacts"])
