from fastapi.testclient import TestClient

from app.main import app


def _register_and_login(client: TestClient, email: str = "user@example.com", password: str = "testpass123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return r.json()["access_token"]


def test_register_creates_user():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/auth/register", json={"email": "new@example.com", "password": "testpass123"}
        )
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "new@example.com"
        assert "id" in body
        assert "hashed_password" not in body  # never leak the hash


def test_register_duplicate_email_rejected():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "testpass123"})
        r = client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "testpass123"})
        assert r.status_code == 400


def test_register_short_password_rejected():
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": "short"})
        assert r.status_code == 422


def test_login_success_returns_token():
    with TestClient(app) as client:
        token = _register_and_login(client, "login@example.com")
        assert token
        assert isinstance(token, str)


def test_login_wrong_password_rejected():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={"email": "wp@example.com", "password": "testpass123"})
        r = client.post("/api/v1/auth/login", data={"username": "wp@example.com", "password": "wrongpass"})
        assert r.status_code == 401


def test_login_nonexistent_user_rejected():
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/login", data={"username": "nobody@example.com", "password": "whatever"})
        assert r.status_code == 401


def test_me_requires_valid_token():
    with TestClient(app) as client:
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert r.status_code == 401


def test_me_returns_current_user_with_valid_token():
    with TestClient(app) as client:
        token = _register_and_login(client, "me@example.com")
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "me@example.com"


def test_history_requires_auth():
    with TestClient(app) as client:
        r = client.get("/api/v1/history")
        assert r.status_code == 401


def test_history_empty_for_new_user():
    with TestClient(app) as client:
        token = _register_and_login(client, "history@example.com")
        r = client.get("/api/v1/history", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []
