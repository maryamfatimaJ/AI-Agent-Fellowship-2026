import pytest

from app.agent.orchestrator import run_agent_turn
from app.guardrails import GuardrailBlockedError
from app.models.assistant import Assistant
from app.models.conversation import Conversation
from app.models.guardrail_event import GuardrailAction, GuardrailEvent, PendingAction, PendingActionStatus
from app.models.trace import Trace, TraceType
from app.models.user import User
from app.models.workspace import Workspace
from app.services.llm_service import AgentGenerationResult, LLMError, ToolCallRequest


def _make_conversation(db_session):
    user = User(email="agent@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    workspace = Workspace(owner_id=user.id, name="WS")
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    assistant = Assistant(workspace_id=workspace.id, name="Assistant")
    db_session.add(assistant)
    db_session.commit()
    db_session.refresh(assistant)

    conversation = Conversation(workspace_id=workspace.id, assistant_id=assistant.id, created_by=user.id)
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    return conversation, assistant, user.id


def _sequenced(monkeypatch, results):
    calls = {"count": 0}

    def _fake(*args, **kwargs):
        index = min(calls["count"], len(results) - 1)
        calls["count"] += 1
        result = results[index]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("app.agent.orchestrator.generate_with_tools", _fake)
    return calls


def test_agent_answers_directly_when_no_tool_is_needed(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(monkeypatch, [AgentGenerationResult(text="The answer is 4.", input_tokens=10, output_tokens=5)])

    user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "What is 2+2?", user_id, db_session
    )

    assert assistant_message.content == "The answer is 4."
    assert outcome.steps == []
    assert outcome.pending_action_id is None
    assert outcome.hit_loop_limit is False

    trace = db_session.query(Trace).filter(Trace.trace_type == TraceType.TOOL_CALL).first()
    assert trace is not None
    assert trace.status.value == "success"


def test_agent_calls_a_low_risk_tool_then_answers(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(
        monkeypatch,
        [
            AgentGenerationResult(
                text=None,
                tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "refund"})],
            ),
            AgentGenerationResult(text="Based on the search, the refund window is 30 days."),
        ],
    )

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "What is the refund policy?", user_id, db_session
    )

    assert len(outcome.steps) == 1
    assert outcome.steps[0].tool_name == "search_documents"
    assert outcome.steps[0].error is None
    assert "30 days" in assistant_message.content


def test_high_risk_tool_creates_a_pending_action_instead_of_executing(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(
        monkeypatch,
        [
            AgentGenerationResult(
                text=None,
                tool_calls=[ToolCallRequest(id="1", name="delete_document", arguments={"document_id": "doc-1"})],
            )
        ],
    )

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "Delete doc-1", user_id, db_session
    )

    assert outcome.pending_action_id is not None
    pending = db_session.query(PendingAction).filter(PendingAction.id == outcome.pending_action_id).first()
    assert pending is not None
    assert pending.status == PendingActionStatus.PENDING
    assert pending.tool_name == "delete_document"
    assert pending.risk_level == "high"
    assert "approval" in assistant_message.content.lower()


def test_repeated_identical_tool_call_triggers_loop_prevention(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    repeated_call = AgentGenerationResult(
        text=None,
        tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "same"})],
    )
    _sequenced(monkeypatch, [repeated_call, repeated_call, repeated_call])

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "Search for same thing repeatedly", user_id, db_session
    )

    assert outcome.hit_loop_limit is True
    assert len(outcome.steps) == 1  # only the first call actually executes; the repeat is refused


def test_tool_error_is_fed_back_and_agent_recovers(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(
        monkeypatch,
        [
            AgentGenerationResult(
                text=None,
                tool_calls=[
                    ToolCallRequest(id="1", name="run_skill", arguments={"skill_name": "Nonexistent", "input_text": "x"})
                ],
            ),
            AgentGenerationResult(text="I couldn't find that skill, so here's a direct answer instead."),
        ],
    )

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "Run the Nonexistent skill", user_id, db_session
    )

    assert outcome.steps[0].error is not None
    assert "direct answer" in assistant_message.content


def test_hitting_max_iterations_without_a_final_answer_stops_gracefully(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)

    def _always_new_search(*args, **kwargs):
        _always_new_search.count = getattr(_always_new_search, "count", 0) + 1
        return AgentGenerationResult(
            text=None,
            tool_calls=[
                ToolCallRequest(id=str(_always_new_search.count), name="search_documents", arguments={"query": f"q{_always_new_search.count}"})
            ],
        )

    monkeypatch.setattr("app.agent.orchestrator.generate_with_tools", _always_new_search)

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "Keep searching forever", user_id, db_session
    )

    assert outcome.hit_loop_limit is True
    assert "allowed number of steps" in assistant_message.content


def test_llm_failure_degrades_to_a_clean_message(db_session, monkeypatch):
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(monkeypatch, [LLMError("simulated outage")])

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "Hello?", user_id, db_session
    )

    assert "try again" in assistant_message.content.lower()
    trace = db_session.query(Trace).filter(Trace.trace_type == TraceType.TOOL_CALL).first()
    assert trace.status.value == "error"


def test_agent_path_input_guard_blocks_empty_message(db_session, monkeypatch):
    """The input guard (app/guardrails/input_guard.py) is wired into the agent
    path exactly like the plain-chat path — this was a real gap before this
    phase (run_agent_turn never called check_input at all)."""
    conversation, assistant, user_id = _make_conversation(db_session)

    with pytest.raises(GuardrailBlockedError):
        run_agent_turn(conversation, assistant, "   ", user_id, db_session)

    event = db_session.query(GuardrailEvent).filter(GuardrailEvent.conversation_id == conversation.id).first()
    assert event is not None
    assert event.action == GuardrailAction.BLOCKED


def test_agent_path_output_guard_redacts_a_leaked_secret(db_session, monkeypatch):
    """The output guard is wired into the agent path so a secret the model
    echoes back (e.g. one embedded in a tool result) is redacted before the
    assistant message is ever persisted — mirroring chat_service.py's
    existing behavior, not a separate/duplicate guard system."""
    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(
        monkeypatch,
        [AgentGenerationResult(text="Sure, here you go: sk-abcdefghijklmnopqrstuvwxyz123456")],
    )

    _user_message, assistant_message, outcome = run_agent_turn(
        conversation, assistant, "What's the key?", user_id, db_session
    )

    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in assistant_message.content
    event = (
        db_session.query(GuardrailEvent)
        .filter(GuardrailEvent.conversation_id == conversation.id, GuardrailEvent.guardrail_type == "secret_leak")
        .first()
    )
    assert event is not None


def test_tool_execution_timeout_is_recovered_from(db_session, monkeypatch):
    """Failure injection: a tool that hangs past app.core.config.Settings.tool_timeout_seconds
    must not freeze the whole agent turn — it should surface as a normal
    ToolResult(error=...) that the agent can recover from, just like a
    functional tool error (test_tool_error_is_fed_back_and_agent_recovers)."""
    import time

    from app.core.config import get_settings

    conversation, assistant, user_id = _make_conversation(db_session)
    _sequenced(
        monkeypatch,
        [
            AgentGenerationResult(
                text=None,
                tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "slow"})],
            ),
            AgentGenerationResult(text="That search took too long, so here's what I know without it."),
        ],
    )

    def _hangs(*args, **kwargs):
        time.sleep(1.0)
        return None

    monkeypatch.setattr("app.agent.orchestrator.execute_tool", _hangs)
    get_settings.cache_clear()
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "0.1")

    try:
        _user_message, assistant_message, outcome = run_agent_turn(
            conversation, assistant, "Search for something slow", user_id, db_session
        )
    finally:
        get_settings.cache_clear()

    assert outcome.steps[0].error is not None
    assert "timed out" in outcome.steps[0].error
    assert "took too long" in assistant_message.content


def test_malformed_tool_call_json_falls_back_to_empty_arguments(monkeypatch):
    """Failure injection: a provider that returns syntactically invalid JSON
    for a tool call's arguments must not crash generate_with_tools — it
    should fall back to an empty-args tool call rather than raising, so the
    agent loop can still proceed (the tool itself will then reject the
    missing required argument, a normal functional failure it already
    recovers from)."""
    from dataclasses import dataclass

    from app.services.llm_service import generate_with_tools

    @dataclass
    class _FakeFunction:
        name: str
        arguments: str

    @dataclass
    class _FakeToolCall:
        id: str
        function: _FakeFunction

    @dataclass
    class _FakeMessage:
        content: str | None
        tool_calls: list

    @dataclass
    class _FakeChoice:
        message: _FakeMessage

    @dataclass
    class _FakeResponse:
        choices: list
        usage: None = None

    fake_response = _FakeResponse(
        choices=[
            _FakeChoice(
                message=_FakeMessage(
                    content=None,
                    tool_calls=[_FakeToolCall(id="1", function=_FakeFunction(name="search_documents", arguments="{not valid json"))],
                )
            )
        ]
    )

    class _FakeCompletions:
        def create(self, **kwargs):
            return fake_response

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr("app.services.llm_service._get_openai_client", lambda: _FakeClient())

    result = generate_with_tools(
        system_prompt="test",
        history=[{"role": "user", "content": "search"}],
        tools=[{"name": "search_documents", "description": "d", "parameters": {}}],
        provider="openai",
    )

    assert result.tool_calls[0].name == "search_documents"
    assert result.tool_calls[0].arguments == {}
