# schemas/user.py — request/response shapes for §Account (spec: /api/users/me)
#
# UserOut is THE security boundary for user data: routes declare
# response_model=UserOut, and FastAPI serializes ONLY these five fields.
# password_hash and created_at have no slot here, so they cannot leak —
# an allowlist, not a "remember to delete the hash" blocklist.

from pydantic import EmailStr, Field

from schemas.base import CamelModel


class UserOut(CamelModel):
    """Response shape: { id, email, fullName, role, hasCompletedSetup }"""

    id: int
    email: EmailStr
    full_name: str          # serializes as "fullName" (alias from CamelModel)
    role: str
    has_completed_setup: bool


class UserUpdate(CamelModel):
    """PATCH /api/users/me body: { fullName?, email?, password? }
    Every field optional — only what the client sends gets updated
    (the route uses model_dump(exclude_unset=True) to tell)."""

    full_name: str | None = None
    email: EmailStr | None = None
    # Same 8-char floor as RegisterIn — rules apply wherever passwords are SET
    # (never on LoginIn, which must accept whatever was registered).
    password: str | None = Field(default=None, min_length=8)


class SetupOut(CamelModel):
    """PATCH /api/users/me/setup response: { id, hasCompletedSetup }"""

    id: int
    has_completed_setup: bool


class AccountDelete(CamelModel):
    """DELETE /api/users/me body: { password }.

    The account password re-supplied as confirmation. Deletion is
    irreversible, so a valid token alone isn't enough — the handler verifies
    this against the stored hash (step-up re-auth) before removing anything,
    which defends the shared/unlocked-device case."""

    password: str
