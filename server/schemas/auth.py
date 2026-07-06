# schemas/auth.py — request/response shapes for §Auth (spec: /api/auth/*)

from typing import Literal

from pydantic import EmailStr, Field

from schemas.base import CamelModel
from schemas.user import UserOut


class RegisterIn(CamelModel):
    """POST /api/auth/register body: { email, password, fullName, role }
    All fields required (no defaults), so a missing one -> 422 automatically."""

    email: EmailStr
    # Minimum length only, no complexity rules — team decision 2026-07-06:
    # empty passwords were registrable before; composition rules hurt 65+
    # users more than they help security.
    password: str = Field(min_length=8)
    full_name: str  # arrives as "fullName" in JSON (CamelModel alias)
    # Literal = the API-boundary twin of the DB's CHECK constraint: same rule,
    # enforced earlier, as a clean 422 instead of a database error.
    role: Literal["primary", "contact"]


class LoginIn(CamelModel):
    """POST /api/auth/login body: { email, password }"""

    email: EmailStr
    password: str


class AuthOut(CamelModel):
    """Register/login response: { token, user: { id, email, fullName, ... } }
    Schemas nest — user is a full UserOut, so the hash-dropping allowlist
    applies here too."""

    token: str
    user: UserOut
