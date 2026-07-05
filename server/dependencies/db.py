# dependencies/db.py — get_db: one database session per request
#
# Express equivalent: middleware that attaches a client to req and releases it
# when the response finishes. Here, any route that declares
#     session: AsyncSession = Depends(get_db)
# gets a fresh session before the handler runs, and cleanup is guaranteed after.

from db.engine import AsyncSessionLocal


async def get_db():
    # Everything before `yield` runs BEFORE the handler (setup),
    # everything after it runs AFTER the response (teardown) — even on errors.
    # `async with` closes the session on exit; if the handler raised without
    # committing, closing rolls the transaction back, so a half-failed request
    # never leaves half-written rows.
    async with AsyncSessionLocal() as session:
        yield session
