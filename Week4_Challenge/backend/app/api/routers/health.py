"""GET /health — liveness/readiness probe."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.settings import get_settings
from app.models.run_store import active_run_count
from app.schemas.api import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(status="ok", llm_provider=settings.llm_provider, active_runs=active_run_count())
