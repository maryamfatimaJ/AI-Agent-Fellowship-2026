from app.core.rate_limit import limiter


def test_login_is_rate_limited_after_five_attempts_per_minute(client):
    """Disabled by default (see conftest._reset_rate_limiter) so the rest of the suite
    isn't throttled; explicitly re-enabled here to prove the limit actually engages."""
    client.post("/api/auth/register", json={"email": "ratelimit@example.com", "password": "pass1234"})

    limiter.enabled = True
    try:
        statuses = [
            client.post(
                "/api/auth/login", json={"email": "ratelimit@example.com", "password": "pass1234"}
            ).status_code
            for _ in range(6)
        ]
    finally:
        limiter.enabled = False

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_register_is_rate_limited_after_ten_attempts_per_minute(client):
    limiter.enabled = True
    try:
        statuses = [
            client.post(
                "/api/auth/register",
                json={"email": f"ratelimit-reg-{i}@example.com", "password": "pass1234"},
            ).status_code
            for i in range(11)
        ]
    finally:
        limiter.enabled = False

    assert statuses[:10] == [201] * 10
    assert statuses[10] == 429
