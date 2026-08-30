from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_create_and_list_prompt_versions(client):
    token = register_and_login(client, "pv-a@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.post(
        f"/api/workspaces/{workspace_id}/prompt-versions",
        json={"name": "Baseline", "version_label": "v1", "system_prompt": "You are a helpful assistant."},
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    listed = client.get(f"/api/workspaces/{workspace_id}/prompt-versions", headers=auth_headers(token)).json()
    assert len(listed) == 1
    assert listed[0]["version_label"] == "v1"
    assert listed[0]["is_active"] is False


def test_activating_a_version_deactivates_others(client):
    token = register_and_login(client, "pv-b@example.com")
    workspace_id = _create_workspace(client, token)

    ids = []
    for label in ["v1", "v2"]:
        resp = client.post(
            f"/api/workspaces/{workspace_id}/prompt-versions",
            json={"name": label, "version_label": label, "system_prompt": f"Prompt {label}"},
            headers=auth_headers(token),
        )
        ids.append(resp.json()["id"])

    client.patch(
        f"/api/workspaces/{workspace_id}/prompt-versions/{ids[0]}",
        json={"is_active": True},
        headers=auth_headers(token),
    )
    client.patch(
        f"/api/workspaces/{workspace_id}/prompt-versions/{ids[1]}",
        json={"is_active": True},
        headers=auth_headers(token),
    )

    versions = client.get(f"/api/workspaces/{workspace_id}/prompt-versions", headers=auth_headers(token)).json()
    active = [v for v in versions if v["is_active"]]
    assert len(active) == 1
    assert active[0]["id"] == ids[1]


def test_prompt_versions_isolated_between_workspaces(client):
    token = register_and_login(client, "pv-c@example.com")
    workspace_a = _create_workspace(client, token)
    workspace_b = _create_workspace(client, token)

    client.post(
        f"/api/workspaces/{workspace_a}/prompt-versions",
        json={"name": "v1", "version_label": "v1", "system_prompt": "x"},
        headers=auth_headers(token),
    )
    versions_b = client.get(f"/api/workspaces/{workspace_b}/prompt-versions", headers=auth_headers(token)).json()
    assert versions_b == []


def test_update_nonexistent_prompt_version_404s(client):
    token = register_and_login(client, "pv-d@example.com")
    workspace_id = _create_workspace(client, token)
    response = client.patch(
        f"/api/workspaces/{workspace_id}/prompt-versions/does-not-exist",
        json={"is_active": True},
        headers=auth_headers(token),
    )
    assert response.status_code == 404
