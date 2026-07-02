# TODO: implement per spec §Auth
#   - POST /api/auth/register  { email, password, fullName, role } -> { token, user } 201
#   - POST /api/auth/login     { email, password }                 -> { token, user } 200

from fastapi import APIRouter

# router = APIRouter(prefix="/auth", tags=["auth"])
