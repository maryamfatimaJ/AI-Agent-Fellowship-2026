def test_register_and_login(client):
    register_response = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "s3cret-pass", "full_name": "Test User"},
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["email"] == "user@example.com"
    assert "hashed_password" not in body

    login_response = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "s3cret-pass"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_login_with_wrong_password_fails(client):
    client.post(
        "/api/auth/register",
        json={"email": "user2@example.com", "password": "correct-pass"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "user2@example.com", "password": "wrong-pass"}
    )
    assert response.status_code == 401


def test_duplicate_registration_conflicts(client):
    client.post("/api/auth/register", json={"email": "dup@example.com", "password": "pass1234"})
    response = client.post("/api/auth/register", json={"email": "dup@example.com", "password": "pass1234"})
    assert response.status_code == 409


def test_logout_revokes_token(client):
    client.post(
        "/api/auth/register",
        json={"email": "logout@example.com", "password": "pass1234"},
    )
    login_response = client.post(
        "/api/auth/login", json={"email": "logout@example.com", "password": "pass1234"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Token works before logout
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    logout_response = client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    # Same token is rejected after logout, even though it hasn't naturally expired
    me_after_logout = client.get("/api/auth/me", headers=headers)
    assert me_after_logout.status_code == 401


def test_logout_does_not_affect_other_tokens(client):
    client.post(
        "/api/auth/register",
        json={"email": "multisession@example.com", "password": "pass1234"},
    )
    token_a = client.post(
        "/api/auth/login", json={"email": "multisession@example.com", "password": "pass1234"}
    ).json()["access_token"]
    token_b = client.post(
        "/api/auth/login", json={"email": "multisession@example.com", "password": "pass1234"}
    ).json()["access_token"]

    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token_a}"})

    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"}).status_code == 200
