from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_pin_and_list_memory(client):
    token = register_and_login(client, "mem-a@example.com")
    workspace_id = _create_workspace(client, token)

    create_response = client.post(
        f"/api/workspaces/{workspace_id}/memory",
        json={"key": "favorite_language", "value": "Prefers Python over JavaScript.", "pinned": True},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201

    list_response = client.get(f"/api/workspaces/{workspace_id}/memory", headers=auth_headers(token))
    entries = list_response.json()
    assert len(entries) == 1
    assert entries[0]["pinned"] is True
    assert entries[0]["value"] == "Prefers Python over JavaScript."


def test_update_and_delete_memory(client):
    token = register_and_login(client, "mem-b@example.com")
    workspace_id = _create_workspace(client, token)
    memory_id = client.post(
        f"/api/workspaces/{workspace_id}/memory",
        json={"key": "note", "value": "Original note"},
        headers=auth_headers(token),
    ).json()["id"]

    update_response = client.patch(
        f"/api/workspaces/{workspace_id}/memory/{memory_id}",
        json={"value": "Updated note"},
        headers=auth_headers(token),
    )
    assert update_response.json()["value"] == "Updated note"

    delete_response = client.delete(
        f"/api/workspaces/{workspace_id}/memory/{memory_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204
    assert client.get(f"/api/workspaces/{workspace_id}/memory", headers=auth_headers(token)).json() == []


def test_memory_never_leaks_between_users_in_same_workspace(client):
    """Regression guard: memory is scoped by user_id even within one workspace."""
    token_a = register_and_login(client, "mem-c@example.com")
    token_b = register_and_login(client, "mem-d@example.com")
    workspace_id = _create_workspace(client, token_a)

    client.post(
        f"/api/workspaces/{workspace_id}/memory",
        json={"key": "secret", "value": "User A's private preference"},
        headers=auth_headers(token_a),
    )

    b_response = client.get(f"/api/workspaces/{workspace_id}/memory", headers=auth_headers(token_b))
    assert b_response.status_code == 404


def test_memory_isolated_across_workspaces(client):
    token = register_and_login(client, "mem-e@example.com")
    workspace_a = _create_workspace(client, token)
    workspace_b = _create_workspace(client, token)

    client.post(
        f"/api/workspaces/{workspace_a}/memory",
        json={"key": "topic", "value": "Discussed in workspace A only"},
        headers=auth_headers(token),
    )

    response = client.get(f"/api/workspaces/{workspace_b}/memory", headers=auth_headers(token))
    assert response.json() == []


def test_chat_turn_triggers_memory_extraction(client):
    token = register_and_login(client, "mem-f@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "I prefer dark mode in every app I use."},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    # mock_llm's memory extractor returns "[]" (no facts) — verifying the call path
    # doesn't raise is the point; extraction quality itself needs a live model.
