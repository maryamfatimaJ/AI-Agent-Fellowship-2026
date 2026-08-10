"""Custom exception hierarchy covering every failure mode the platform must
handle explicitly: timeouts, tool failures, search failures, upstream API
failures, duplicate tasks, missing evidence, invalid JSON, invalid structured
output, and empty results.

Every exception carries a machine-readable `code` so the supervisor recovery
logic and the execution trace can categorize failures without string
matching on messages.
"""

from __future__ import annotations


class EvidentError(Exception):
    """Base class for all Evident domain errors."""

    code: str = "evident_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class LLMTimeoutError(EvidentError):
    code = "llm_timeout"


class LLMAPIError(EvidentError):
    code = "llm_api_error"


class InvalidJSONError(EvidentError):
    code = "invalid_json"


class InvalidStructuredOutputError(EvidentError):
    code = "invalid_structured_output"


class ToolExecutionError(EvidentError):
    code = "tool_execution_error"


class SearchFailureError(ToolExecutionError):
    code = "search_failure"


class EmptyResultError(EvidentError):
    code = "empty_result"


class DuplicateTaskError(EvidentError):
    code = "duplicate_task"


class MissingEvidenceError(EvidentError):
    code = "missing_evidence"


class WorkflowTerminatedError(EvidentError):
    code = "workflow_terminated"


class RunNotFoundError(EvidentError):
    code = "run_not_found"


class InvalidWorkflowStateError(EvidentError):
    code = "invalid_workflow_state"
