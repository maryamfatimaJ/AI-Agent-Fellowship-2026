"""Citation Validator Tool — checks that every evidence citation referenced
in a block of text (report markdown, analysis output) points at a real,
known evidence_id. Used to catch hallucinated citations before they reach
the user."""

from __future__ import annotations

import re

from pydantic import BaseModel

_CITATION_RE = re.compile(r"\bev_[a-f0-9]{6,12}\b")


class CitationValidationResult(BaseModel):
    is_valid: bool
    cited_ids: list[str]
    invalid_ids: list[str]


def validate_citations(text: str, valid_evidence_ids: list[str]) -> CitationValidationResult:
    valid_set = set(valid_evidence_ids)
    cited = sorted(set(_CITATION_RE.findall(text)))
    invalid = [cid for cid in cited if cid not in valid_set]
    return CitationValidationResult(is_valid=not invalid, cited_ids=cited, invalid_ids=invalid)
