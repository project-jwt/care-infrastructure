# core/security.py — password hashing + JWT creation/verification
#
# Express equivalents: bcryptjs for the first pair, and this whole file
# REPLACES cookie-session for the second pair. There is no session store:
# the signed token itself is the proof of identity, re-verified on every
# request by checking its signature against JWT_SECRET.

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from config import settings

# ── Passwords (bcrypt) ───────────────────────────────────────────────────────
# CryptContext is passlib's hasher registry. deprecated="auto" means: if we
# ever switch schemes, old hashes still verify but get flagged for re-hashing.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """One-way hash for storage in users.password_hash.
    bcrypt generates a random salt per call, so the same password hashes
    differently every time — that's expected, verify() handles it.
    Express equivalent: bcrypt.hashSync(plain, 10)
    """
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a login attempt against the stored hash (never decrypts —
    re-hashes the attempt with the same salt and compares).
    Express equivalent: bcrypt.compareSync(plain, hashed)
    """
    return pwd_context.verify(plain, hashed)


# ── Tokens (JWT, HS256) ──────────────────────────────────────────────────────


def create_access_token(user_id: int, role: str) -> str:
    """Mint a signed token at register/login. The payload's three claims:
      sub  - "subject", whose token this is (JWT spec says it must be a string)
      role - 'primary' | 'contact', so role checks don't need a DB query
      exp  - expiry timestamp; jwt.decode() rejects the token after this moment
    Payload is READABLE by anyone (base64, not encrypted) — never put
    secrets in it. The signature only makes it unforgeable.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Verify signature + expiry and return the payload dict.
    Raises jose.JWTError if the token is tampered with, expired, or garbage —
    dependencies/auth.py catches that and turns it into a 401.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
