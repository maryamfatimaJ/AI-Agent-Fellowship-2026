from app.models.trace import Trace, TraceType
from app.services.llm_service import AgentGenerationResult, ToolCallRequest
from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_agent_mode_end_to_end_through_the_api(client, monkeypatch):
    monkeypatch.setattr(
        "app.agent.orchestrator.generate_with_tools",
        lambda *a, **k: AgentGenerationResult(text="Direct answer, no tools needed."),
    )

    token = register_and_login(client, "agent-a@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hello", "mode": "agent"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assistant_message"]["content"] == "Direct answer, no tools needed."
    assert body["agent_steps"] == []
    assert body["pending_action_id"] is None


def test_high_risk_tool_call_requires_approval_before_executing(client, monkeypatch):
    monkeypatch.setattr(
        "app.agent.orchestrator.generate_with_tools",
        lambda *a, **k: AgentGenerationResult(
            text=None,
            tool_calls=[ToolCallRequest(id="1", name="delete_document", arguments={"document_id": "doc-1"})],
        ),
    )

    token = register_and_login(client, "agent-b@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Delete doc-1", "mode": "agent"},
        headers=auth_headers(token),
    )
    body = response.json()
    action_id = body["pending_action_id"]
    assert action_id is not None

    pending = client.get(
        f"/api/workspaces/{workspace_id}/pending-actions", params={"status": "pending"}, headers=auth_headers(token)
    ).json()
    assert len(pending) == 1
    assert pending[0]["id"] == action_id

    decision = client.post(
        f"/api/workspaces/{workspace_id}/pending-actions/{action_id}/decision",
        json={"approve": False},
        headers=auth_headers(token),
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"

    # a second decision on the same action is refused
    repeat = client.post(
        f"/api/workspaces/{workspace_id}/pending-actions/{action_id}/decision",
        json={"approve": True},
        headers=auth_headers(token),
    )
    assert repeat.status_code == 409


def test_pending_actions_are_isolated_between_workspaces(client, monkeypatch):
    monkeypatch.setattr(
        "app.agent.orchestrator.generate_with_tools",
        lambda *a, **k: AgentGenerationResult(
            text=None,
            tool_calls=[ToolCallRequest(id="1", name="delete_document", arguments={"document_id": "doc-1"})],
        ),
    )
    token = register_and_login(client, "agent-c@example.com")
    workspace_a = _create_workspace(client, token)
    workspace_b = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_a}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_a}/conversations/{conversation_id}/messages",
        json={"content": "Delete doc-1", "mode": "agent"},
        headers=auth_headers(token),
    )

    pending_b = client.get(f"/api/workspaces/{workspace_b}/pending-actions", headers=auth_headers(token)).json()
    assert pending_b == []


def test_agent_mode_records_a_tool_call_trace(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.agent.orchestrator.generate_with_tools",
        lambda *a, **k: AgentGenerationResult(text="Answer."),
    )
    token = register_and_login(client, "agent-d@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hi", "mode": "agent"},
        headers=auth_headers(token),
    )

    traces = client.get(
        f"/api/workspaces/{workspace_id}/traces", params={"trace_type": "tool_call"}, headers=auth_headers(token)
    ).json()
    assert traces["total"] == 1
