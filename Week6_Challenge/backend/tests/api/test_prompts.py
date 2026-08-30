from tests.conftest import auth_headers, register_and_login


def _create_workspace(client, token):
    return client.post("/api/workspaces", json={"name": "WS"}, headers=auth_headers(token)).json()["id"]


def test_workspace_is_seeded_with_default_prompts(client):
    token = register_and_login(client, "prompt-a@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.get(f"/api/workspaces/{workspace_id}/prompts", headers=auth_headers(token))
    prompts = response.json()
    assert len(prompts) == 4
    assert {p["category"] for p in prompts} == {"education", "programming", "writing", "research"}


def test_create_update_delete_prompt(client):
    token = register_and_login(client, "prompt-b@example.com")
    workspace_id = _create_workspace(client, token)

    create_response = client.post(
        f"/api/workspaces/{workspace_id}/prompts",
        json={"name": "Custom prompt", "content": "Do the thing.", "category": "business"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    prompt_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/workspaces/{workspace_id}/prompts/{prompt_id}",
        json={"content": "Do the updated thing."},
        headers=auth_headers(token),
    )
    assert update_response.json()["content"] == "Do the updated thing."

    delete_response = client.delete(
        f"/api/workspaces/{workspace_id}/prompts/{prompt_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204


def test_filter_prompts_by_category(client):
    token = register_and_login(client, "prompt-c@example.com")
    workspace_id = _create_workspace(client, token)

    response = client.get(f"/api/workspaces/{workspace_id}/prompts?category=writing", headers=auth_headers(token))
    prompts = response.json()
    assert len(prompts) == 1
    assert prompts[0]["category"] == "writing"


def test_prompts_isolated_between_users(client):
    token_a = register_and_login(client, "prompt-d@example.com")
    token_b = register_and_login(client, "prompt-e@example.com")
    workspace_id = _create_workspace(client, token_a)

    response = client.get(f"/api/workspaces/{workspace_id}/prompts", headers=auth_headers(token_b))
    assert response.status_code == 404
