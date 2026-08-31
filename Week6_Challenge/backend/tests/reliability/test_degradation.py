"""Failure-injection tests for the platform's graceful-degradation paths.

Each test monkeypatches a specific dependency to simulate a real outage (a
provider SDK exception is exactly what these look like in production) and
asserts the system degrades cleanly — the user-facing request still succeeds
where the requirement is "keep going without that feature," and the failure
is recorded as a trace rather than silently lost or surfaced as a raw 500.
"""

from app.services.llm_service import LLMError, LLMTimeoutError
from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_llm_provider_outage_degrades_to_a_clean_fallback_message(client, monkeypatch):
    """Scenario 1: the LLM provider is unreachable/times out mid-chat. The
    endpoint must still return 200 with a sanitized user-facing message —
    never a raw 500 — and the failure must show up in the traces table."""

    def _raise_timeout(*args, **kwargs):
        raise LLMTimeoutError("simulated provider timeout")

    monkeypatch.setattr("app.services.chat_service.generate_reply", _raise_timeout)

    token = register_and_login(client, "degrade-a@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hello?"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    content = response.json()["assistant_message"]["content"].lower()
    assert "try again" in content or "temporarily" in content
    assert "simulated provider timeout" not in content  # never leak raw provider errors

    traces = client.get(
        f"/api/workspaces/{workspace_id}/traces", params={"trace_type": "chat"}, headers=auth_headers(token)
    ).json()
    assert traces["items"][0]["status"] == "timeout"


def test_rag_embedding_outage_degrades_to_an_answer_without_citations(client, monkeypatch):
    """Scenario 2: the embedding provider fails during RAG retrieval for a chat
    turn. The turn must still complete normally, just without RAG context,
    instead of failing the whole request."""
    token = register_and_login(client, "degrade-b@example.com")
    workspace_id = _create_workspace(client, token)

    # Ingest a document first, while embeddings still work (mock_llm's default
    # behavior), so there are real chunks to (fail to) retrieve against.
    upload = client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", b"Refund policy details for the project.", "text/plain")},
        headers=auth_headers(token),
    )
    assert upload.json()["status"] == "ready"

    def _raise_embedding_outage(*args, **kwargs):
        raise LLMError("simulated embedding outage")

    monkeypatch.setattr("app.rag.retrieval.embed_texts", _raise_embedding_outage)

    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "What is the refund policy?"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["citations"] is None
    # The user must be told search itself is down, not just silently handed
    # an uncited answer indistinguishable from "nothing relevant was found".
    assert "temporarily unavailable" in response.json()["assistant_message"]["content"]

    embedding_traces = client.get(
        f"/api/workspaces/{workspace_id}/traces",
        params={"trace_type": "embedding"},
        headers=auth_headers(token),
    ).json()
    assert any(item["status"] == "degraded" for item in embedding_traces["items"])


def test_memory_extraction_outage_does_not_break_the_chat_turn(client, monkeypatch):
    """Scenario 3: the memory-extraction LLM call (which runs after every chat
    reply) fails. The chat turn itself must still succeed and return the
    assistant's real reply — extraction failures never surface to the user."""

    def _raise(*args, **kwargs):
        raise LLMError("simulated memory extraction outage")

    monkeypatch.setattr("app.memory.memory_service.generate_reply", _raise)

    token = register_and_login(client, "degrade-c@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Remember that I like tea."},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "Mock assistant reply."

    memory_traces = client.get(
        f"/api/workspaces/{workspace_id}/traces",
        params={"trace_type": "memory_extraction"},
        headers=auth_headers(token),
    ).json()
    assert memory_traces["items"][0]["status"] == "degraded"
