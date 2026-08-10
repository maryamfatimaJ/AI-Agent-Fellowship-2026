"""Deterministic-shape ID generators for runs, tasks, evidence, and log entries."""

from __future__ import annotations

import uuid


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def new_task_id(index: int) -> str:
    return f"task_{index:03d}_{uuid.uuid4().hex[:6]}"


def new_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex[:10]}"


def new_log_id() -> str:
    return f"log_{uuid.uuid4().hex[:10]}"


def new_handoff_id() -> str:
    return f"ho_{uuid.uuid4().hex[:10]}"
