"""Centralized exception handling — maps domain errors to the appropriate
HTTP status codes instead of leaking 500s for expected failure modes."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.logging_config import get_logger
from app.utils.errors import (
    EvidentError,
    InvalidWorkflowStateError,
    RunNotFoundError,
)

logger = get_logger("api.errors")

_STATUS_BY_ERROR = {
    RunNotFoundError: 404,
    InvalidWorkflowStateError: 409,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EvidentError)
    async def handle_evident_error(request: Request, exc: EvidentError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), 500)
        logger.warning(
            "http.evident_error",
            path=request.url.path,
            code=exc.code,
            message=exc.message,
            status_code=status_code,
        )
        return JSONResponse(status_code=status_code, content={"error": exc.to_dict()})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("http.unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
        )
