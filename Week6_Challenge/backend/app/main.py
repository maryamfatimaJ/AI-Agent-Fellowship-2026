import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routers import (
    assistants,
    auth,
    conversations,
    dashboard,
    documents,
    evaluations,
    guardrails,
    health,
    memory,
    models,
    prompt_versions,
    prompts,
    quality,
    skills,
    traces,
    workspaces,
)
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.rate_limit import limiter
from app.core.tracing_middleware import TracingMiddleware
from app.database.base import Base
from app.database.lightweight_migrations import sync_missing_columns
from app.database.session import engine

# Registers every ORM model on Base.metadata, including ones no router imports
# directly yet (e.g. Trace) — required so create_all() below creates their tables.
import app.models  # noqa: E402,F401

configure_logging()
logger = logging.getLogger("app")

settings = get_settings()

# Foundation-stage schema creation; a real migration tool (Alembic) replaces
# this once the schema needs versioned, reversible changes.
Base.metadata.create_all(bind=engine)
# create_all() never alters an already-existing table — this adds any new
# nullable columns introduced since the table was first created (see
# app/database/lightweight_migrations.py for why this exists instead of a
# destructive recreate or a full Alembic setup).
sync_missing_columns(engine, Base)

app = FastAPI(title="AI Workspace Platform", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last so it ends up outermost (Starlette wraps middleware in reverse
# registration order), giving it visibility into every request's true total
# latency, including CORS handling.
app.add_middleware(TracingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(models.router)
app.include_router(workspaces.router)
app.include_router(assistants.router)
app.include_router(conversations.router)
app.include_router(documents.router)
app.include_router(memory.router)
app.include_router(prompts.router)
app.include_router(skills.router)
app.include_router(dashboard.router)
app.include_router(traces.router)
app.include_router(guardrails.router)
app.include_router(evaluations.router)
app.include_router(prompt_versions.router)
app.include_router(quality.router)


@app.get("/")
def root() -> dict:
    return {"name": "AI Workspace Platform API", "status": "running"}
