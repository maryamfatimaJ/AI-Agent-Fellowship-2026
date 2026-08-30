from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    response = client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token))
    return response.json()["id"]


def test_conversation_persists_messages_and_gets_a_default_title(client):
    token = register_and_login(client, "conv-a@example.com")
    workspace_id = _create_workspace(client, token)

    create_response = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]
    assert create_response.json()["title"] is None

    message_response = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "What is the meaning of life?"},
        headers=auth_headers(token),
    )
    assert message_response.status_code == 200
    body = message_response.json()
    assert body["user_message"]["content"] == "What is the meaning of life?"
    assert body["assistant_message"]["content"] == "Mock assistant reply."
    assert body["assistant_message"]["role"] == "assistant"

    detail_response = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(token)
    )
    detail = detail_response.json()
    assert detail["title"] == "What is the meaning of life?"
    assert len(detail["messages"]) == 2


def test_conversation_survives_a_simulated_relogin(client):
    token = register_and_login(client, "conv-b@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Remember this conversation."},
        headers=auth_headers(token),
    )

    new_token = client.post(
        "/api/auth/login", json={"email": "conv-b@example.com", "password": "pass1234"}
    ).json()["access_token"]

    response = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(new_token)
    )
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 2


def test_rename_and_delete_conversation(client):
    token = register_and_login(client, "conv-c@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    rename_response = client.patch(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}",
        json={"title": "Renamed"},
        headers=auth_headers(token),
    )
    assert rename_response.json()["title"] == "Renamed"

    delete_response = client.delete(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(token)
    )
    assert get_response.status_code == 404


def test_search_conversations_by_title_and_message_content(client):
    token = register_and_login(client, "conv-d@example.com")
    workspace_id = _create_workspace(client, token)

    conv_1 = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={"title": "Trip planning"}, headers=auth_headers(token)
    ).json()["id"]
    conv_2 = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={"title": "Budget review"}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conv_2}/messages",
        json={"content": "Let's talk about the trip to Japan"},
        headers=auth_headers(token),
    )

    by_title = client.get(
        f"/api/workspaces/{workspace_id}/conversations?q=planning", headers=auth_headers(token)
    ).json()
    assert {c["id"] for c in by_title} == {conv_1}

    by_content = client.get(
        f"/api/workspaces/{workspace_id}/conversations?q=Japan", headers=auth_headers(token)
    ).json()
    assert {c["id"] for c in by_content} == {conv_2}


def test_conversation_isolated_between_users(client):
    token_a = register_and_login(client, "conv-e@example.com")
    token_b = register_and_login(client, "conv-f@example.com")
    workspace_id = _create_workspace(client, token_a)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token_a)
    ).json()["id"]

    response = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(token_b)
    )
    assert response.status_code == 404
