# tests/conftest.py — shared fixtures for the backend test suite.
#
# The app is Postgres+asyncpg in prod, but these tests run against a throwaway
# in-memory SQLite database: no external service, and the inbox query is plain
# portable SQL (joins, WHERE, ORDER BY, column projection) that behaves the
# same on both. A single StaticPool connection keeps one in-memory DB alive
# for the whole test — the default would give each connection its own empty DB.

import os

# Make settings load without a real .env (CI-safe). setdefault won't clobber a
# developer's existing env; the sqlite URL below is never connected to — every
# test overrides get_db onto the in-memory engine.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("RESEND_API_KEY", "test-key")  # required since email-send landed

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import models  # noqa: F401  — registers every table on Base.metadata
from db.base import Base
from dependencies.db import get_db
from main import app


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def sessions(engine):
    """A session factory bound to the test engine (like prod's AsyncSessionLocal)."""
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(sessions):
    """One open session, for model-layer tests that seed and query in place."""
    async with sessions() as s:
        yield s


@pytest_asyncio.fixture
async def client(sessions):
    """httpx client driving the real app in-process, with get_db pointed at the
    test engine. ASGITransport doesn't run lifespan, so the prod Postgres
    create_all never fires — the engine fixture builds the schema instead."""

    async def override_get_db():
        async with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
