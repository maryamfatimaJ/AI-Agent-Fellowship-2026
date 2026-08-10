"""In-process registry of runs.

Tracks, per run_id (== LangGraph thread_id): when it was created, its last
known workflow_status, and an asyncio lock preventing two concurrent
invocations against the same checkpointer thread (which LangGraph does not
support safely).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.state.graph_state import ResearchState


@dataclass
class RunRecord:
    run_id: str
    created_at: str
    user_request: str
    initial_state: ResearchState
    status: str = "received"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_REGISTRY: dict[str, RunRecord] = {}


def register_run(record: RunRecord) -> None:
    _REGISTRY[record.run_id] = record


def get_run(run_id: str) -> RunRecord | None:
    return _REGISTRY.get(run_id)


def all_runs() -> list[RunRecord]:
    return list(_REGISTRY.values())


def active_run_count() -> int:
    terminal = {"completed", "failed", "rejected"}
    return sum(1 for record in _REGISTRY.values() if record.status not in terminal)
