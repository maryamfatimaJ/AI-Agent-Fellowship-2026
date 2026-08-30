def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_unknown_route_returns_404(client):
    response = client.get("/api/this-route-does-not-exist")
    assert response.status_code == 404


def test_protected_route_without_token_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
