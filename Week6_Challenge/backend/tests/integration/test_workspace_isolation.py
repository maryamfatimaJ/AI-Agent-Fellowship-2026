def _register_and_login(client, email: str, password: str = "pass1234") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_user_cannot_access_another_users_workspace(client):
    token_a = _register_and_login(client, "owner-a@example.com")
    token_b = _register_and_login(client, "owner-b@example.com")

    create_response = client.post(
        "/api/workspaces", json={"name": "Owner A's Workspace"}, headers=_auth_headers(token_a)
    )
    assert create_response.status_code == 201
    workspace_id = create_response.json()["id"]

    forbidden_response = client.get(f"/api/workspaces/{workspace_id}", headers=_auth_headers(token_b))
    assert forbidden_response.status_code == 404

    owner_response = client.get(f"/api/workspaces/{workspace_id}", headers=_auth_headers(token_a))
    assert owner_response.status_code == 200


def test_workspace_list_is_scoped_to_owner(client):
    token_a = _register_and_login(client, "list-a@example.com")
    token_b = _register_and_login(client, "list-b@example.com")

    client.post("/api/workspaces", json={"name": "A's Workspace"}, headers=_auth_headers(token_a))
    client.post("/api/workspaces", json={"name": "B's Workspace 1"}, headers=_auth_headers(token_b))
    client.post("/api/workspaces", json={"name": "B's Workspace 2"}, headers=_auth_headers(token_b))

    a_workspaces = client.get("/api/workspaces", headers=_auth_headers(token_a)).json()
    b_workspaces = client.get("/api/workspaces", headers=_auth_headers(token_b)).json()

    assert len(a_workspaces) == 1
    assert len(b_workspaces) == 2


def test_unauthenticated_request_is_rejected(client):
    response = client.get("/api/workspaces")
    assert response.status_code == 401
