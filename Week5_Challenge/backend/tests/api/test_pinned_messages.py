from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_pin_and_list_pinned_messages(client):
    token = register_and_login(client, "pin-a@example.com")
    workspace_id = _create_workspace(client, token)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    message_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Pin this one"},
        headers=auth_headers(token),
    ).json()["user_message"]["id"]

    pin_response = client.patch(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages/{message_id}",
        json={"pinned": True},
        headers=auth_headers(token),
    )
    assert pin_response.json()["pinned"] is True

    pinned_response = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/pinned-messages",
        headers=auth_headers(token),
    )
    assert len(pinned_response.json()) == 1

    unpin_response = client.patch(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages/{message_id}",
        json={"pinned": False},
        headers=auth_headers(token),
    )
    assert unpin_response.json()["pinned"] is False


def test_cannot_pin_message_in_another_users_conversation(client):
    token_a = register_and_login(client, "pin-b@example.com")
    token_b = register_and_login(client, "pin-c@example.com")
    workspace_id = _create_workspace(client, token_a)
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token_a)
    ).json()["id"]
    message_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hello"},
        headers=auth_headers(token_a),
    ).json()["user_message"]["id"]

    response = client.patch(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages/{message_id}",
        json={"pinned": True},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404
