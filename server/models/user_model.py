# models/user_model.py — the users table (spec §Schema Design) + query helpers
#
# Express equivalent: models/user.js — except instead of SQL strings like
# 'SELECT * FROM users WHERE email = $1', the table is described ONCE as a
# class, and queries are built from it.

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base):
    # Inheriting Base registers this table in Base.metadata (see db/base.py).
    __tablename__ = "users"

    # Table-level constraints that don't belong to a single column.
    # Same as the spec's: role TEXT CHECK (role IN ('primary', 'contact'))
    __table_args__ = (
        CheckConstraint("role IN ('primary', 'contact')", name="users_role_check"),
    )

    # Each attribute below becomes a column. The pattern is:
    #   name: Mapped[python_type] = mapped_column(<column type/options>)
    # Mapped[int] / Mapped[str] give the Python type; mapped_column carries
    # what you'd write in CREATE TABLE (primary key, unique, defaults).

    # API contract uses `id`, the spec's schema uses `user_id`. We get both:
    # the first argument to mapped_column overrides the column name, so
    # Python code says user.id while the actual DB column is user_id.
    # Mapped[int] + primary_key on Postgres = SERIAL (auto-increment).
    id: Mapped[int] = mapped_column("user_id", primary_key=True)

    email: Mapped[str] = mapped_column(Text, unique=True)      # TEXT UNIQUE NOT NULL
    password_hash: Mapped[str] = mapped_column(Text)           # TEXT NOT NULL (bcrypt output, never a raw password)
    full_name: Mapped[str] = mapped_column(Text)               # TEXT NOT NULL
    role: Mapped[str] = mapped_column(Text)                    # 'primary' | 'contact' (constrained above)

    # NOT NULL comes free: Mapped[str] means required, Mapped[str | None] would
    # mean nullable. server_default (vs plain default=) puts DEFAULT false in
    # the table itself, so even inserts that bypass Python get the default.
    has_completed_setup: Mapped[bool] = mapped_column(server_default=text("false"))

    # DateTime(timezone=True) = TIMESTAMPTZ. Without it, Mapped[datetime] maps
    # to a zone-less TIMESTAMP and "when did this happen" becomes ambiguous.
    # server_default=func.now() -> DEFAULT now(): the DATABASE stamps the time.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Query helpers ────────────────────────────────────────────────────────────
# The functions routers call — same role as the functions exported from an
# Express model file. Every helper takes the request's AsyncSession first:
# the CALLER owns the session/transaction, the model just uses it. Routers get
# theirs from Depends(get_db) and pass it down.


async def find(session: AsyncSession, user_id: int) -> User | None:
    """Look up a user by primary key. Returns None if no such user.

    session.get(Model, pk) is the built-in primary-key shortcut:
    SELECT * FROM users WHERE user_id = $1
    """
    return await session.get(User, user_id)


async def find_by_email(session: AsyncSession, email: str) -> User | None:
    """Look up a user by email. Returns None if no account has that email.

    select(User).where(...) builds: SELECT * FROM users WHERE email = $1
    (User.email == email is overloaded to produce a parameterized SQL condition,
    not a boolean — injection-safe, same as $1 placeholders in pg.)
    scalar_one_or_none() unpacks the result set: the one matching User, or None.
    """
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession, email: str, password_hash: str, full_name: str, role: str
) -> User:
    """Insert a new user and return it with DB-generated fields populated.

    Takes password_hash, not a raw password — hashing is core/security.py's job;
    the model never sees plaintext.
    """
    user = User(email=email, password_hash=password_hash, full_name=full_name, role=role)
    session.add(user)         # track this new object — no SQL yet
    await session.commit()    # INSERT ... happens here, in the transaction
    await session.refresh(user)  # SELECT back what the DB generated: id, created_at
    return user


async def update(session: AsyncSession, user_id: int, **fields) -> User | None:
    """Update any subset of a user's columns. Returns the updated user,
    or None if no such user.

    **fields collects keyword args into a dict (like a JS rest/spread param):
        update(session, 1, full_name="Eleanor P.", email="e@aol.com")
        -> fields == {"full_name": "Eleanor P.", "email": "e@aol.com"}
    No explicit UPDATE statement: the session has been tracking the object
    since .get() loaded it, sees which attributes changed, and emits
    UPDATE users SET <only the changed columns> at commit.
    """
    user = await session.get(User, user_id)
    if user is None:
        return None
    for name, value in fields.items():
        setattr(user, name, value)  # dynamic user.full_name = value, like obj[key] = value
    await session.commit()
    return user


async def mark_setup_complete(session: AsyncSession, user_id: int) -> User | None:
    """Flip has_completed_setup to true (PATCH /api/users/me/setup).
    Just a named special case of update(), so the router reads as intent."""
    return await update(session, user_id, has_completed_setup=True)
