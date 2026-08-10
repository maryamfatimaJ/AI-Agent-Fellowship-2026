"""Tool unit tests — calculator, citation validator, CSV reader, document
reader, JSON extraction, search, content extraction, and the evidence
store/retrieval round-trip."""

from __future__ import annotations

import pytest

from app.schemas.evidence import EvidenceItem
from app.tools.calculator_tool import calculate
from app.tools.citation_validator_tool import validate_citations
from app.tools.csv_reader_tool import read_csv_text
from app.tools.document_reader_tool import read_document
from app.tools.evidence_retrieval_tool import retrieve_evidence
from app.tools.evidence_store_tool import store_evidence
from app.utils.errors import InvalidJSONError, ToolExecutionError
from app.utils.json_utils import extract_json_object


# --- calculator_tool ---------------------------------------------------------


def test_calculate_basic_arithmetic():
    assert calculate("(120 - 100) / 100 * 100") == 20.0


def test_calculate_rejects_non_arithmetic_input():
    with pytest.raises(ToolExecutionError):
        calculate("__import__('os').system('echo hi')")


def test_calculate_rejects_name_references():
    with pytest.raises(ToolExecutionError):
        calculate("open('secrets.txt')")


# --- citation_validator_tool -----------------------------------------------


def test_validate_citations_all_valid():
    result = validate_citations("See ev_abc123 and ev_def456.", ["ev_abc123", "ev_def456"])
    assert result.is_valid
    assert result.invalid_ids == []
    assert set(result.cited_ids) == {"ev_abc123", "ev_def456"}


def test_validate_citations_flags_unknown_ids():
    result = validate_citations("See ev_abc123 and ev_ffffff.", ["ev_abc123"])
    assert not result.is_valid
    assert result.invalid_ids == ["ev_ffffff"]


# --- csv_reader_tool ---------------------------------------------------------


def test_read_csv_text_parses_rows():
    rows = read_csv_text("name,value\nfoo,1\nbar,2\n")
    assert rows == [{"name": "foo", "value": "1"}, {"name": "bar", "value": "2"}]


def test_read_csv_text_respects_max_rows():
    rows = read_csv_text("name\na\nb\nc\n", max_rows=2)
    assert len(rows) == 2


# --- document_reader_tool ----------------------------------------------------


def test_read_document_reads_supported_file(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# Hello\nWorld", encoding="utf-8")
    content = read_document(str(path))
    assert "Hello" in content


def test_read_document_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "data.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(ToolExecutionError):
        read_document(str(path))


# --- json_utils ---------------------------------------------------------------


def test_extract_json_object_from_fenced_block():
    raw = 'Here is the answer:\n```json\n{"a": 1, "b": "x"}\n```'
    assert extract_json_object(raw) == {"a": 1, "b": "x"}


def test_extract_json_object_from_raw_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_object_strips_trailing_commas():
    assert extract_json_object('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_extract_json_object_raises_on_garbage():
    with pytest.raises(InvalidJSONError):
        extract_json_object("not json at all")


def test_extract_json_object_raises_on_empty():
    with pytest.raises(InvalidJSONError):
        extract_json_object("")


# --- evidence store / retrieval round-trip -----------------------------------


async def test_evidence_store_and_retrieval_round_trip():
    item = EvidenceItem(
        evidence_id="ev_test0001",
        claim="Test claim",
        supporting_text="Test excerpt",
        source="https://example.com",
        source_title="Example",
        retrieved_at="2026-01-01T00:00:00+00:00",
        research_question="Is X true?",
        confidence=75,
        agent_id="research",
    )

    stored_count = await store_evidence("run_test", [item])
    assert stored_count == 1

    retrieved = await retrieve_evidence("run_test")
    assert len(retrieved) == 1
    assert retrieved[0].evidence_id == "ev_test0001"


async def test_evidence_retrieval_empty_for_unknown_run():
    retrieved = await retrieve_evidence("run_does_not_exist")
    assert retrieved == []
