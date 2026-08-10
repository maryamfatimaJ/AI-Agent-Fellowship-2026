"""Evident backend — FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_middleware import register_exception_handlers
from app.api.middleware.logging_middleware import RequestLoggingMiddleware
from app.api.routers import (
    approval,
    clarification,
    evidence,
    health,
    logs,
    report,
    research,
    tasks,
    workflow,
)
from app.config.logging_config import configure_logging, get_logger
from app.config.settings import get_settings

configure_logging()
logger = get_logger("app.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("app.startup", llm_provider=settings.llm_provider, app_env=settings.app_env)
    yield


app = FastAPI(
    title="Evident — Multi-Agent Research & Decision Intelligence Platform",
    description=(
        "LangGraph-orchestrated backend coordinating a Supervisor, Research, "
        "Analyst, Critic, Report Writer, and optional specialist agents to "
        "turn research questions into evidence-grounded decision briefs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)

app.include_router(research.router)
app.include_router(clarification.router)
app.include_router(workflow.router)
app.include_router(tasks.router)
app.include_router(evidence.router)
app.include_router(logs.router)
app.include_router(report.router)
app.include_router(approval.router)
app.include_router(health.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.app_env == "development")
