# TODO: implement per spec §Account
#   - GET   /api/users/me         -> current user
#   - PATCH /api/users/me         -> update fullName/email/password
#   - PATCH /api/users/me/setup   -> flip hasCompletedSetup to true

from fastapi import APIRouter

# router = APIRouter(prefix="/users", tags=["users"])
