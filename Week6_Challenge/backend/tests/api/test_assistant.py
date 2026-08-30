from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    response = client.post(
        "/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)
    )
    return response.json()["id"]


def test_assistant_is_auto_created_with_workspace(client):
    token = register_and_login(client, "assistant-a@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.get(f"/api/workspaces/{workspace_id}/assistant", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Assistant"
    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 1024


def test_assistant_config_is_persisted(client):
    token = register_and_login(client, "assistant-b@example.com")
    workspace_id = _create_workspace(client, token)

    update_response = client.patch(
        f"/api/workspaces/{workspace_id}/assistant",
        json={
            "name": "Research Buddy",
            "role": "Research assistant",
            "system_prompt": "Be concise and cite sources.",
            "personality": "warm but efficient",
            "response_style": "detailed",
            "temperature": 0.3,
            "max_tokens": 2048,
        },
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200

    get_response = client.get(f"/api/workspaces/{workspace_id}/assistant", headers=auth_headers(token))
    body = get_response.json()
    assert body["name"] == "Research Buddy"
    assert body["role"] == "Research assistant"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 2048


def test_assistant_config_is_isolated_between_users(client):
    token_a = register_and_login(client, "assistant-c@example.com")
    token_b = register_and_login(client, "assistant-d@example.com")
    workspace_id = _create_workspace(client, token_a)

    response = client.get(f"/api/workspaces/{workspace_id}/assistant", headers=auth_headers(token_b))
    assert response.status_code == 404
