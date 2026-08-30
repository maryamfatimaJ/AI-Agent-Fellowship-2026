from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_chat_message_records_a_trace(client):
    token = register_and_login(client, "trace-a@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hello there"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    traces_response = client.get(
        f"/api/workspaces/{workspace_id}/traces", params={"trace_type": "chat"}, headers=auth_headers(token)
    )
    assert traces_response.status_code == 200
    body = traces_response.json()
    assert body["total"] == 1
    trace = body["items"][0]
    assert trace["trace_type"] == "chat"
    assert trace["status"] == "success"
    assert trace["conversation_id"] == conversation_id
    assert trace["latency_ms"] >= 0
    assert trace["meta"]["rag_ms"] is not None
    assert trace["meta"]["llm_ms"] is not None
    # Memory extraction runs as a FastAPI background task on the real HTTP path
    # (performance optimization — see chat_service.send_message), so its
    # latency is no longer part of the chat trace's own meta...
    assert trace["meta"]["memory_backgrounded"] is True

    # ...but TestClient runs background tasks to completion before returning,
    # so the memory-extraction trace it records independently is still visible.
    memory_traces = client.get(
        f"/api/workspaces/{workspace_id}/traces",
        params={"trace_type": "memory_extraction"},
        headers=auth_headers(token),
    ).json()
    assert memory_traces["total"] == 1

    # Trace spans: the canonical execution timeline the trace viewer renders.
    span_names = [span["name"] for span in trace["meta"]["spans"]]
    assert span_names == ["request", "input_validation", "retrieval", "model_call", "memory_extraction", "final_response"]
    for span in trace["meta"]["spans"]:
        assert "duration_ms" in span
        assert "status" in span
    assert trace["meta"]["prompt_version"] == "unversioned"
    assert trace["meta"]["input_preview"] == "Hello there"
    assert isinstance(trace["meta"]["retrieved_document_ids"], list)


def test_agent_turn_records_tool_call_spans(client, monkeypatch):
    from app.services.llm_service import AgentGenerationResult, ToolCallRequest

    call_state = {"n": 0}

    def _sequenced(*a, **k):
        call_state["n"] += 1
        if call_state["n"] == 1:
            return AgentGenerationResult(
                text=None, tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "refund"})]
            )
        return AgentGenerationResult(text="Here you go.")

    monkeypatch.setattr("app.agent.orchestrator.generate_with_tools", _sequenced)

    token = register_and_login(client, "trace-f@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "search for refund info", "mode": "agent"},
        headers=auth_headers(token),
    )

    traces = client.get(
        f"/api/workspaces/{workspace_id}/traces", params={"trace_type": "tool_call"}, headers=auth_headers(token)
    ).json()
    assert traces["total"] == 1
    span_names = [span["name"] for span in traces["items"][0]["meta"]["spans"]]
    assert span_names == [
        "request",
        "input_validation",
        "agent_decision",
        "tool_call",
        "tool_result",
        "agent_decision",
        "final_response",
    ]


def test_traces_isolated_between_workspaces(client):
    token = register_and_login(client, "trace-b@example.com")
    workspace_a = _create_workspace(client, token)
    workspace_b = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_a}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_a}/conversations/{conversation_id}/messages",
        json={"content": "Only in workspace A"},
        headers=auth_headers(token),
    )

    traces_response = client.get(f"/api/workspaces/{workspace_b}/traces", headers=auth_headers(token))
    assert traces_response.json()["total"] == 0


def test_traces_require_ownership(client):
    token_a = register_and_login(client, "trace-c@example.com")
    token_b = register_and_login(client, "trace-d@example.com")
    workspace_id = _create_workspace(client, token_a)

    response = client.get(f"/api/workspaces/{workspace_id}/traces", headers=auth_headers(token_b))
    assert response.status_code == 404


def test_running_a_skill_records_a_trace(client):
    token = register_and_login(client, "trace-e@example.com")
    workspace_id = _create_workspace(client, token)
    skills = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token)).json()
    skill_id = skills[0]["id"]

    client.post(
        f"/api/workspaces/{workspace_id}/skills/{skill_id}/run",
        json={"input": "Summarize this."},
        headers=auth_headers(token),
    )

    traces_response = client.get(
        f"/api/workspaces/{workspace_id}/traces",
        params={"trace_type": "skill"},
        headers=auth_headers(token),
    )
    body = traces_response.json()
    assert body["total"] == 1
    assert body["items"][0]["trace_type"] == "skill"
