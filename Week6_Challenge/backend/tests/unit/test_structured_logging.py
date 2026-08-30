"""Structured-logging tests: confirm log_event() emits records carrying the
event name and context fields, and that JSONFormatter serializes them as
queryable JSON (not just a free-text message)."""

import json
import logging

from app.core.events import MODEL_CALLED, log_event
from app.core.logging_config import JSONFormatter


def test_log_event_attaches_event_name_and_fields_as_extra(caplog):
    logger = logging.getLogger("test.events")
    with caplog.at_level(logging.INFO, logger="test.events"):
        log_event(logger, MODEL_CALLED, provider="gemini", model="gemini-2.5-flash")

    record = caplog.records[0]
    assert record.event == MODEL_CALLED
    assert record.provider == "gemini"
    assert record.model == "gemini-2.5-flash"


def test_json_formatter_includes_extra_fields_as_top_level_json_keys():
    logger = logging.getLogger("test.json_events")
    record = logger.makeRecord(
        "test.json_events",
        logging.INFO,
        __file__,
        1,
        "tool_selected",
        (),
        None,
        extra={"event": "tool_selected", "tool_name": "search_documents", "risk_level": "low"},
    )
    payload = json.loads(JSONFormatter().format(record))
    assert payload["event"] == "tool_selected"
    assert payload["tool_name"] == "search_documents"
    assert payload["risk_level"] == "low"
    assert payload["message"] == "tool_selected"


def test_json_formatter_never_crashes_on_unserializable_extra_values():
    logger = logging.getLogger("test.json_events")
    record = logger.makeRecord(
        "test.json_events", logging.INFO, __file__, 1, "evt", (), None, extra={"weird": object()}
    )
    payload = json.loads(JSONFormatter().format(record))
    assert "weird" in payload  # stringified fallback, not a crash


def test_real_chat_request_emits_the_expected_event_sequence(client, caplog):
    """Integration check: a real chat turn through the real HTTP endpoint
    actually emits request_received, retrieval_started/completed,
    model_called, and request_completed — not just unit-tested in isolation."""
    from tests.conftest import auth_headers, register_and_login

    with caplog.at_level(logging.INFO):
        token = register_and_login(client, "events-a@example.com")
        workspace_id = client.post(
            "/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)
        ).json()["id"]
        conversation_id = client.post(
            f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
        ).json()["id"]
        client.post(
            f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
            json={"content": "Hello"},
            headers=auth_headers(token),
        )

    # model_called isn't expected here: the mock_llm fixture replaces
    # chat_service.generate_reply directly (the call-site reference), which
    # bypasses llm_service.generate_reply (where model_called is logged)
    # entirely — see test_model_called_event_fires_from_the_real_llm_service
    # below for that one, exercised directly against llm_service instead.
    events = {getattr(r, "event", None) for r in caplog.records}
    for expected in ("request_received", "request_completed", "retrieval_started", "retrieval_completed"):
        assert expected in events, f"missing event: {expected}"


def test_model_called_event_fires_from_the_real_llm_service(caplog):
    """model_called is logged inside llm_service.generate_reply() itself,
    before dispatching to a provider — fires even when the provider call
    then fails (e.g. no/invalid API key), since logging happens first."""
    from app.services.llm_service import LLMError, generate_reply

    with caplog.at_level(logging.INFO):
        try:
            generate_reply(system_prompt="hi", history=[], provider="gemini")
        except LLMError:
            pass  # expected in a test environment with no real API key

    events = {getattr(r, "event", None) for r in caplog.records}
    assert "model_called" in events


def test_tool_events_fire_during_a_real_agent_turn(db_session, mock_llm, monkeypatch, caplog):
    """tool_selected and tool_succeeded/tool_failed fire from the real
    orchestrator, not just from a mocked call site."""
    from app.api.routers.assistants import get_or_create_assistant
    from app.evaluation.seed import create_eval_workspace, ensure_eval_user
    from app.models.workspace import Workspace
    from app.agent.orchestrator import run_agent_turn
    from app.models.conversation import Conversation
    from app.services.llm_service import AgentGenerationResult, ToolCallRequest

    owner = ensure_eval_user(db_session)
    workspace_id = create_eval_workspace(db_session, owner)
    workspace = db_session.query(Workspace).filter(Workspace.id == workspace_id).first()
    assistant = get_or_create_assistant(workspace, db_session)
    conversation = Conversation(workspace_id=workspace_id, created_by=owner.id)
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    monkeypatch.setattr(
        "app.agent.orchestrator.generate_with_tools",
        lambda *a, **k: AgentGenerationResult(
            text=None, tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "refund"})]
        ),
    )

    with caplog.at_level(logging.INFO):
        run_agent_turn(conversation, assistant, "search for refund info", owner.id, db_session)

    events = {getattr(r, "event", None) for r in caplog.records}
    assert "tool_selected" in events
    assert "tool_succeeded" in events or "tool_failed" in events


def test_retry_attempted_event_fires_on_a_transient_failure_then_succeeds():
    from app.core.retry import call_with_retry

    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("503 Service Unavailable")
        return "ok"

    import logging as _logging

    logger = _logging.getLogger()
    records = []

    class _Collector(_logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Collector()
    logger.addHandler(handler)
    try:
        call_with_retry(flaky)
    finally:
        logger.removeHandler(handler)

    events = {getattr(r, "event", None) for r in records}
    assert "retry_attempted" in events
