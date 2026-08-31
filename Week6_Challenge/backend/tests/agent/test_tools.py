"""Failure injection at the tool-execution boundary (app/agent/tools.py).
Complements tests/agent/test_orchestrator.py's functional tool-error test
(a missing skill) with a genuine unexpected-exception scenario — e.g. a
database error while a tool handler is running — proving execute_tool's
catch-all never lets a request crash uncaught."""

from sqlalchemy.exc import OperationalError

from app.agent.tools import execute_tool
from app.rag.retrieval import RagUnavailableError


def test_execute_tool_catches_a_database_error_and_returns_a_safe_result(db_session, monkeypatch):
    def _raises_db_error(workspace_id, query, db):
        raise OperationalError("SELECT 1", {}, Exception("database is locked"))

    monkeypatch.setattr("app.agent.tools.retrieve_relevant_chunks", _raises_db_error)

    result = execute_tool(
        "search_documents",
        {"query": "anything"},
        workspace_id="ws-1",
        user_id="user-1",
        db=db_session,
    )

    assert result.output is None
    assert result.error is not None
    assert "database is locked" in result.error


def test_search_documents_reports_a_clear_unavailable_error_when_rag_degrades(db_session, monkeypatch):
    """Graceful degradation (Requirement 20) at the tool boundary: a search
    backend outage must be reported as a distinct, clear error rather than
    silently returning {"results": []}, which would look identical to
    "nothing matched" from the agent's/user's perspective."""

    def _raises_rag_unavailable(workspace_id, query, db):
        raise RagUnavailableError("Knowledge search is temporarily unavailable: simulated outage")

    monkeypatch.setattr("app.agent.tools.retrieve_relevant_chunks", _raises_rag_unavailable)

    result = execute_tool(
        "search_documents",
        {"query": "refund policy"},
        workspace_id="ws-1",
        user_id="user-1",
        db=db_session,
    )

    assert result.output is None
    assert result.error is not None
    assert "temporarily unavailable" in result.error


def test_search_documents_returns_an_explicit_empty_result_not_an_error(db_session):
    """Failure injection (Requirement 16): "tool returns empty result" is a
    dedicated, real scenario — a query against a workspace with no matching
    (or no) documents must come back as a normal ToolResult(output={"results":
    []}, error=None), never conflated with a tool exception/failure. Uses the
    real retrieve_relevant_chunks (not monkeypatched) against a workspace_id
    that owns zero documents, so this exercises the actual empty-result code
    path, not a simulated one."""
    result = execute_tool(
        "search_documents",
        {"query": "anything"},
        workspace_id="workspace-with-no-documents",
        user_id="user-1",
        db=db_session,
    )

    assert result.error is None
    assert result.output == {"results": []}


def test_execute_tool_returns_an_error_for_an_unregistered_tool_name(db_session):
    result = execute_tool("not_a_real_tool", {}, workspace_id="ws-1", user_id="user-1", db=db_session)
    assert result.error == "Unknown tool 'not_a_real_tool'"
