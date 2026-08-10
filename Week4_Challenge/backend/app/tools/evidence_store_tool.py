"""Evidence Store Tool — the Research Agent's write path for persisting
evidence as it is discovered."""

from __future__ import annotations

from app.config.logging_config import get_logger
from app.schemas.evidence import EvidenceItem
from app.services import evidence_service

logger = get_logger("tools.evidence_store")


async def store_evidence(run_id: str, items: list[EvidenceItem]) -> int:
    """Persist evidence items for a run. Returns the count stored."""

    if not items:
        return 0
    evidence_service.save_evidence(run_id, items)
    logger.info("evidence_store.saved", run_id=run_id, count=len(items))
    return len(items)
