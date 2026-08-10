"""GET /evidence/{run_id} — all evidence collected so far, served from the
Evidence Retrieval tool (the durable, run_id-keyed evidence store)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import EvidenceListOut
from app.services import workflow_service
from app.tools.evidence_retrieval_tool import retrieve_evidence

router = APIRouter(tags=["evidence"])


@router.get("/evidence/{run_id}", response_model=EvidenceListOut)
async def get_evidence(run_id: str) -> EvidenceListOut:
    workflow_service.ensure_run_exists(run_id)
    evidence = await retrieve_evidence(run_id)
    return EvidenceListOut(run_id=run_id, evidence=evidence)
