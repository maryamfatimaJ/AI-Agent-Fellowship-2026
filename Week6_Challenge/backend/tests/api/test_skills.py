from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_workspace_is_seeded_with_six_default_skills(client):
    token = register_and_login(client, "skill-a@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token))
    skills = response.json()
    assert len(skills) == 6
    assert {s["name"] for s in skills} == {
        "Summarize",
        "Write an email",
        "Generate a report",
        "Meeting notes",
        "Generate ideas",
        "SWOT analysis",
    }


def test_run_skill_standalone_without_conversation(client):
    token = register_and_login(client, "skill-b@example.com")
    workspace_id = _create_workspace(client, token)
    skill_id = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token)).json()[0]["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/skills/{skill_id}/run",
        json={"input": "Some long text to summarize."},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["output"] == "Mock assistant reply."
    assert body["user_message"] is None
    assert body["assistant_message"] is None


def test_run_skill_attached_to_conversation_persists_messages(client):
    token = register_and_login(client, "skill-c@example.com")
    workspace_id = _create_workspace(client, token)
    skill_id = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token)).json()[0]["id"]
    conversation_id = client.post(
        f"/api/workspaces/{workspace_id}/conversations", json={}, headers=auth_headers(token)
    ).json()["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/skills/{skill_id}/run",
        json={"input": "Notes to turn into something.", "conversation_id": conversation_id},
        headers=auth_headers(token),
    )
    body = response.json()
    assert body["user_message"] is not None
    assert body["assistant_message"] is not None

    detail = client.get(
        f"/api/workspaces/{workspace_id}/conversations/{conversation_id}", headers=auth_headers(token)
    ).json()
    assert len(detail["messages"]) == 2


def test_skills_isolated_between_users(client):
    token_a = register_and_login(client, "skill-d@example.com")
    token_b = register_and_login(client, "skill-e@example.com")
    workspace_id = _create_workspace(client, token_a)

    response = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token_b))
    assert response.status_code == 404


def test_run_nonexistent_skill_returns_404(client):
    token = register_and_login(client, "skill-f@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.post(
        f"/api/workspaces/{workspace_id}/skills/does-not-exist/run",
        json={"input": "Some text."},
        headers=auth_headers(token),
    )
    assert response.status_code == 404


def test_run_skill_blocked_for_non_owner(client):
    token_a = register_and_login(client, "skill-g@example.com")
    token_b = register_and_login(client, "skill-h@example.com")
    workspace_id = _create_workspace(client, token_a)
    skill_id = client.get(f"/api/workspaces/{workspace_id}/skills", headers=auth_headers(token_a)).json()[0]["id"]

    response = client.post(
        f"/api/workspaces/{workspace_id}/skills/{skill_id}/run",
        json={"input": "Some text."},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 404
