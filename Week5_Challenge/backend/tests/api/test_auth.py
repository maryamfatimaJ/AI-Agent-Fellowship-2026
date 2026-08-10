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
