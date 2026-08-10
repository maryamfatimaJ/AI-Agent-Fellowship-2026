from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_dashboard_reflects_real_counts_and_usage(client):
    token = register_and_login(client, "dash-a@example.com")
    workspace_id = _create_workspace(client, token)

    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]
    client.post(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
        json={"content": "Hello there"},
        headers=auth_headers(token),
    )
    client.post(
        f"/api/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", b"Some notes about the project.", "text/plain")},
        headers=auth_headers(token),
    )
    client.post(
        f"/api/workspaces/{workspace_id}/memory",
        json={"key": "note", "value": "Remember this."},
        headers=auth_headers(token),
    )

    response = client.get(f"/api/workspaces/{workspace_id}/dashboard", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()

    assert body["counts"]["conversations"] == 1
    assert body["counts"]["messages"] == 2
    assert body["counts"]["documents"] == 1
    assert body["counts"]["memory_items"] == 1
    assert body["counts"]["prompt_templates"] == 4
    assert body["counts"]["skills"] == 6
    assert body["usage"]["total_input_tokens"] > 0
    assert body["usage"]["total_output_tokens"] > 0
    assert len(body["recent_activity"]) > 0


def test_dashboard_isolated_between_workspaces(client):
    token = register_and_login(client, "dash-b@example.com")
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

    response = client.get(f"/api/workspaces/{workspace_b}/dashboard", headers=auth_headers(token))
    body = response.json()
    assert body["counts"]["conversations"] == 0
    assert body["usage"]["total_input_tokens"] == 0
