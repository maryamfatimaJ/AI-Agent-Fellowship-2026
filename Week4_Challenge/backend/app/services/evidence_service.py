"""Evidence persistence engine backing the Evidence Store / Retrieval tools.

An in-memory, per-process store keyed by run_id. This is the right choice
for a single-instance academic deployment; the class boundary is deliberate
so a production deployment can swap in Postgres/Redis without touching
calling code (tools only depend on this module's public functions).
"""

from __future__ import annotations

import threading

from app.schemas.evidence import EvidenceItem

_lock = threading.Lock()
_STORE: dict[str, list[EvidenceItem]] = {}


def save_evidence(run_id: str, items: list[EvidenceItem]) -> None:
    with _lock:
        _STORE.setdefault(run_id, []).extend(items)


def get_evidence(run_id: str) -> list[EvidenceItem]:
    with _lock:
        return list(_STORE.get(run_id, []))


def get_evidence_by_ids(run_id: str, evidence_ids: set[str]) -> list[EvidenceItem]:
    return [item for item in get_evidence(run_id) if item.evidence_id in evidence_ids]


def clear_run(run_id: str) -> None:
    with _lock:
        _STORE.pop(run_id, None)
