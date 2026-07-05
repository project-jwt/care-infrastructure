# db/engine.py — the app's single connection pool + session factory
#
# Express equivalent:
#     const { Pool } = require('pg');
#     const pool = new Pool({ connectionString: process.env.DATABASE_URL });
#
# `engine` plays the role of that Pool: created once at startup, it manages a
# small set of open connections to Postgres and lends one out per query.
#
# `AsyncSessionLocal` has no direct Express equivalent. In Express you called
# pool.query(sql) directly; with SQLAlchemy you talk to a *session* instead —
# a short-lived workspace for one request. You load model objects through it,
# modify them in plain Python, and session.commit() turns those changes into
# SQL inside a transaction. The pattern is: one request -> one session.
# (dependencies/db.py is what actually opens/closes one per request.)

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings

# The +asyncpg part of the URL (postgresql+asyncpg://) is what selects the
# async driver — like choosing the `pg` client library, but encoded in the URL.
engine = create_async_engine(settings.database_url)

# expire_on_commit=False: by default SQLAlchemy marks every object "stale" after
# commit() and re-fetches it from the DB on the next attribute access. Our session
# is already closed by the time FastAPI serializes the response, so that re-fetch
# would crash. This flag keeps the loaded values usable after commit.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
