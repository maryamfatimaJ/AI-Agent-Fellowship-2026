"""Evidence Retrieval Tool — the read path used by the API layer (and
available to any agent that needs evidence outside the graph's own state,
e.g. cross-run analytics)."""

from __future__ import annotations

from app.config.logging_config import get_logger
from app.schemas.evidence import EvidenceItem
from app.services import evidence_service

logger = get_logger("tools.evidence_retrieval")


async def retrieve_evidence(run_id: str) -> list[EvidenceItem]:
    items = evidence_service.get_evidence(run_id)
    logger.info("evidence_retrieval.fetched", run_id=run_id, count=len(items))
    return items


async def retrieve_evidence_by_ids(run_id: str, evidence_ids: list[str]) -> list[EvidenceItem]:
    items = evidence_service.get_evidence_by_ids(run_id, set(evidence_ids))
    logger.info("evidence_retrieval.fetched_by_ids", run_id=run_id, requested=len(evidence_ids), found=len(items))
    return items
