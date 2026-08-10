"""LangGraph checkpointer factory.

`MemorySaver` is the right choice for a single-process academic deployment:
it gives us full `interrupt()`/`Command(resume=...)` support (clarification
and human-approval checkpoints) without an external dependency. Swapping to
`SqliteSaver` or a Postgres-backed checkpointer for multi-process durability
is a one-line change here — no calling code depends on the concrete class.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver


@lru_cache(maxsize=1)
def get_checkpointer() -> MemorySaver:
    return MemorySaver()
