"""Serving the React app, unknown routes and security headers."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import FakePvgis, make_settings


@pytest.fixture
def app_client(tmp_path: Path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Solar sites</title>")
    (static / "assets" / "app.js").write_text("console.log('hi')")
    app = create_app(make_settings(tmp_path, static_dir=static), pvgis=FakePvgis())
    with TestClient(app) as client:
        yield client


def test_the_react_app_is_served_on_every_page_route(app_client: TestClient) -> None:
    for path in ("/", "/login", "/sites/3", "/sites/3/edit"):
        response = app_client.get(path)
        assert response.status_code == 200, path
        assert "<title>Solar sites</title>" in response.text
    assert app_client.get("/assets/app.js").text == "console.log('hi')"


def test_missing_files_and_unknown_api_routes_are_404(app_client: TestClient) -> None:
    assert app_client.get("/assets/missing.js").status_code == 404
    assert app_client.get("/robots.txt").status_code == 404
    response = app_client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_files_outside_the_build_are_never_served(app_client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("secret")
    tricks = (
        "/../secret.txt",
        "/%2e%2e/secret.txt",
        "/assets/../../secret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
    )
    for path in tricks:
        assert "secret" not in app_client.get(path).text, path


def test_wrong_method_on_an_api_route_is_405(app_client: TestClient) -> None:
    # The route exists, but not for PATCH: 405 Method Not Allowed, not 404.
    assert app_client.patch("/api/sites/1").status_code == 405


def test_security_headers(app_client: TestClient) -> None:
    page = app_client.get("/")
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert "script-src 'self'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Frame-Options"] == "DENY"
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert app_client.get("/api/me").headers["Cache-Control"] == "no-store"
