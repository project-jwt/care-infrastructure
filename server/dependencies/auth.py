# dependencies/auth.py — JWT auth as FastAPI dependencies
#
# Express equivalent: the checkAuthentication middleware, but opt-in per route.
# A route declares which guarantee it needs in its signature:
#     user: User = Depends(get_current_user)   -> any logged-in user
#     user: User = Depends(require_primary)    -> logged-in AND role == 'primary'
#     user: User = Depends(require_contact)    -> logged-in AND role == 'contact'
# The handler body then just uses `user` — by the time it runs, identity is proven.

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import decode_token
from dependencies.db import get_db
from models import user_model
from models.user_model import User

# HTTPBearer parses "Authorization: Bearer <token>" and hands us the token part.
# auto_error=False -> a missing header gives None instead of FastAPI's default
# 403, so we control the status code (spec says missing auth = 401).
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Header -> verified token -> loaded User. Raises 401 at any broken link.

    Runs on EVERY protected request — this is the "decode constantly" half of
    JWT (create_access_token in the routers is the "mint rarely" half).
    """
    if credentials is None:  # no Authorization header at all
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(credentials.credentials)  # .credentials = the raw token
        user_id = int(payload["sub"])  # sub is a string (JWT spec) — int() it back
    except (JWTError, KeyError, ValueError):
        # JWTError: bad signature, expired, garbage. KeyError/ValueError: valid
        # signature but no sub / non-numeric sub — still "bad token", still 401,
        # never a 500.
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await user_model.find(session, user_id)
    if user is None:  # valid token for an account that no longer exists
        raise HTTPException(status_code=401, detail="User not found")

    return user


# Role gates: dependencies can depend on dependencies (middleware chaining).
# 403, not 401: "we know who you are (401 already passed) — this resource
# just isn't for your role" (spec: primary-only endpoints reject contacts).


async def require_primary(user: User = Depends(get_current_user)) -> User:
    if user.role != "primary":
        raise HTTPException(status_code=403, detail="Primary account required")
    return user


async def require_contact(user: User = Depends(get_current_user)) -> User:
    if user.role != "contact":
        raise HTTPException(status_code=403, detail="Contact account required")
    return user
