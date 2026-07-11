# main.py — assembles the FastAPI app. Express equivalent: app.js.
#
# Run in dev (from server/):  uvicorn main:app --reload --port 8000
# Auto-docs while running:    http://localhost:8000/docs

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

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


# Registered on the STARLETTE base class, not fastapi.HTTPException: router-
# level errors (unknown path -> 404, wrong method -> 405) raise the parent
# class, which a handler on the subclass never sees — they were escaping as
# {"detail": ...}. One registration on the parent catches both.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
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


# ── Serve the built frontend (single-service deploy) ────────────────────────
# The deploy builds frontend/dist and this app hands it out: API under /api,
# React app for everything else — one service, one URL, no CORS or rewrites.
# Express equivalent: app.use(express.static('build')) + the index.html
# catch-all. Skipped entirely when dist/ doesn't exist (local dev, where Vite
# serves the frontend itself on :5173).

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    # Hashed build assets (JS/CSS bundles) served as plain files.
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    # Catch-all is registered LAST, so real routes (/api/*, /docs) win; it
    # only sees paths nothing else claimed.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Never swallow API misses into index.html — an unknown /api path
        # must stay a JSON 404, not a 200 with HTML.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        # Real files at the dist root (favicon, manifest...) serve as-is.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        # Everything else is a UI path -> the React app decides what to show.
        return FileResponse(FRONTEND_DIST / "index.html")
