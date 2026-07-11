# main.py — assembles the FastAPI app. Express equivalent: app.js.
#
# Run in dev (from server/):  uvicorn main:app --reload --port 8000
# Auto-docs while running:    http://localhost:8000/docs

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from db.base import Base
from db.engine import engine

# Importing the models package registers every table in Base.metadata —
# models/__init__.py imports each model module, so new models added there
# are picked up by create_all with no change to this file.
import models  # noqa: F401
from routers import auth, contacts, received_summaries, summaries, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup (before the first request): create any missing
    # tables. Harmless if they already exist; ALTERing changed tables is a
    # migration-tool job (Alembic, later). Rows/seed data: db/seed.py.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield  # app serves requests while paused here; after = shutdown cleanup
    await engine.dispose()


app = FastAPI(title="Care Infrastructure API", lifespan=lifespan)

# Mount each resource's router under /api (like app.use('/api', router)).
# Final paths: /api/auth/register, /api/users/me, ...
app.include_router(auth.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(received_summaries.router, prefix="/api")
app.include_router(summaries.router, prefix="/api")
app.include_router(users.router, prefix="/api")


# ── Global error shaping ─────────────────────────────────────────────────────
# The spec's error contract is { message }, but FastAPI's defaults emit
# { detail }. These two handlers translate at the boundary so no route has to
# think about it. Express equivalent: the 4-arg error-handling middleware.


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Every raise HTTPException(status_code=..., detail=...) anywhere in the
    # app becomes: <status> { "message": <detail> }
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Schema rejections (bad email, missing field, bad role...) -> 422 with a
    # readable summary of which fields failed, still shaped as { message }.
    problems = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'] if part != 'body')}: {err['msg']}"
        for err in exc.errors()
    )
    return JSONResponse(status_code=422, content={"message": f"Validation failed — {problems}"})
