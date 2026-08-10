"""Custom LangGraph reducers.

`operator.add` (list concatenation) is enough for most accumulating fields.
`completed_tasks` is the one field that must also de-duplicate — every
parallel research_node instance appends its own task_id, and a retried or
re-entrant node must not double-count — so it gets an explicit reducer here.
"""

from __future__ import annotations


def merge_unique_str(existing: list[str] | None, incoming: list[str] | None) -> list[str]:
    """Append-and-deduplicate for string lists (e.g. `completed_tasks`)."""

    existing = existing or []
    incoming = incoming or []
    seen = dict.fromkeys(existing)
    for item in incoming:
        seen[item] = None
    return list(seen.keys())
