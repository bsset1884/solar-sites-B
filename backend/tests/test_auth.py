import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.models import AuthSession, User

from .conftest import errors_of, make_settings, register


def test_register_creates_the_account_and_starts_a_session(client: TestClient) -> None:
    response = client.post(
        "/api/register", json={"email": "  Advisor@Example.com ", "password": "correct horse"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "advisor@example.com"  # trimmed and lower-cased
    assert len(body["csrfToken"]) >= 40

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" not in cookie  # plain http://localhost; set on https

    assert client.get("/api/me").json()["email"] == "advisor@example.com"


def test_register_fails_when_the_email_exists(client: TestClient) -> None:
    register(client, "advisor@example.com")
    response = client.post(
        "/api/register", json={"email": "ADVISOR@example.com", "password": "another password"}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "An account with this email already exists."}


def test_register_validates_each_field(client: TestClient) -> None:
    errors = errors_of(client.post("/api/register", json={"email": "no-at-sign", "password": "short"}))
    assert errors == {
        "email": "Enter a valid email address.",
        "password": "Must be at least 8 characters.",
    }
    errors = errors_of(client.post("/api/register", json={}))
    assert errors == {"email": "This field is required.", "password": "This field is required."}


def test_login_and_me(client: TestClient) -> None:
    register(client, "advisor@example.com", "correct horse")
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401

    response = client.post("/api/login", json={"email": "Advisor@Example.com", "password": "correct horse"})
    assert response.status_code == 200
    csrf = response.json()["csrfToken"]

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"email": "advisor@example.com", "csrfToken": csrf}


def test_wrong_password_and_unknown_email_get_the_same_answer(client: TestClient) -> None:
    register(client, "advisor@example.com", "correct horse")
    client.cookies.clear()
    wrong_password = client.post("/api/login", json={"email": "advisor@example.com", "password": "nope"})
    unknown_email = client.post("/api/login", json={"email": "nobody@example.com", "password": "nope"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Wrong email or password."}
    assert "set-cookie" not in wrong_password.headers


def test_me_without_a_session_is_401(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401
    client.cookies.set("session", "made-up-token")
    assert client.get("/api/me").status_code == 401


def test_logout_needs_the_csrf_token_and_ends_the_session_on_the_server(client: TestClient) -> None:
    csrf = register(client)
    old_cookie = client.cookies.get("session")

    assert client.post("/api/logout").status_code == 403
    assert client.post("/api/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.get("/api/me").status_code == 200  # still logged in

    response = client.post("/api/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/me").status_code == 401

    # Re-using the old cookie does not work: the session was deleted, not just the cookie.
    client.cookies.set("session", old_cookie)
    assert client.get("/api/me").status_code == 401


def test_logout_without_a_session_is_also_204(client: TestClient) -> None:
    assert client.post("/api/logout").status_code == 204


def test_passwords_and_session_tokens_are_not_stored_in_plain_text(client: TestClient, app: FastAPI) -> None:
    register(client, "advisor@example.com", "correct horse")
    token = client.cookies.get("session")
    with app.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert "correct horse" not in user.password_hash
        assert db.get(AuthSession, token) is None  # only the SHA-256 of the token is stored
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 1


def test_a_new_login_replaces_the_old_session_of_that_browser(client: TestClient, app: FastAPI) -> None:
    register(client, "advisor@example.com", "correct horse")
    old_token = client.cookies.get("session")
    client.post("/api/login", json={"email": "advisor@example.com", "password": "correct horse"})
    assert client.cookies.get("session") != old_token
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 1


def test_expired_sessions_are_rejected(client: TestClient, app: FastAPI) -> None:
    register(client)
    with app.state.session_factory() as db:
        db.execute(update(AuthSession).values(expires_at=int(time.time()) - 1))
        db.commit()
    assert client.get("/api/me").status_code == 401


def test_too_many_failed_logins_give_429(tmp_path, fake_pvgis) -> None:
    from app.main import create_app

    app = create_app(make_settings(tmp_path, login_max_failures=3), pvgis=fake_pvgis)
    with TestClient(app) as client:
        register(client, "advisor@example.com", "correct horse")
        client.cookies.clear()
        for _ in range(3):
            bad = client.post("/api/login", json={"email": "advisor@example.com", "password": "guess"})
            assert bad.status_code == 401

        # Now even the right password is refused for a while (no feedback for guessers).
        right = {"email": "advisor@example.com", "password": "correct horse"}
        blocked = client.post("/api/login", json=right)
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0

        # Other accounts are not affected.
        register(client, "other@example.com", "correct horse")
        client.cookies.clear()
        ok = client.post("/api/login", json={"email": "other@example.com", "password": "correct horse"})
        assert ok.status_code == 200
