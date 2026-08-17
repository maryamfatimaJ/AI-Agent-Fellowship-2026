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
    health,
    memory,
    models,
    prompts,
    skills,
    workspaces,
)
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.rate_limit import limiter
from app.database.base import Base
from app.database.session import engine

configure_logging()
logger = logging.getLogger("app")

settings = get_settings()

# Foundation-stage schema creation; a real migration tool (Alembic) replaces
# this once the schema needs versioned, reversible changes.
Base.metadata.create_all(bind=engine)

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


@app.get("/")
def root() -> dict:
    return {"name": "AI Workspace Platform API", "status": "running"}
