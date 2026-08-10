"""Domain representation of a pending clarification — what the workflow is
blocked on while it is paused at the interrupt() boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PendingClarification(BaseModel):
    question: str
    round_number: int
    missing_information: list[str] = Field(default_factory=list)
