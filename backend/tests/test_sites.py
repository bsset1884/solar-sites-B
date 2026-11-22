from fastapi.testclient import TestClient

from .conftest import SITE, create_site, errors_of, register


def test_create_read_update_delete(client: TestClient) -> None:
    csrf = register(client)
    headers = {"X-CSRF-Token": csrf}

    response = client.post("/api/sites", json=SITE, headers=headers)
    assert response.status_code == 201
    site = response.json()
    assert site == {"id": site["id"], **SITE}  # the input fields plus id, camelCase
    assert response.headers["Location"] == f"/api/sites/{site['id']}"

    assert client.get(f"/api/sites/{site['id']}").json() == site
    assert client.get("/api/sites").json() == [site]

    changed = {**SITE, "clientName": "Familie de Vries", "peakKwp": 6.5}
    response = client.put(f"/api/sites/{site['id']}", json=changed, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"id": site["id"], **changed}

    response = client.delete(f"/api/sites/{site['id']}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/sites/{site['id']}").status_code == 404
    assert client.get("/api/sites").json() == []


def test_roof_area_is_optional(client: TestClient) -> None:
    csrf = register(client)
    without_roof = {key: value for key, value in SITE.items() if key != "roofAreaM2"}
    response = client.post("/api/sites", json=without_roof, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    assert response.json()["roofAreaM2"] is None


def test_everything_needs_a_session(client: TestClient) -> None:
    for method, url in [
        ("GET", "/api/sites"),
        ("POST", "/api/sites"),
        ("GET", "/api/sites/1"),
        ("PUT", "/api/sites/1"),
        ("DELETE", "/api/sites/1"),
        ("GET", "/api/sites/1/production"),
        ("GET", "/api/sites/1/battery?capacityKwh=5&annualUseKwh=3000"),
    ]:
        response = client.request(method, url, json=SITE if method in ("POST", "PUT") else None)
        assert response.status_code == 401, (method, url)


def test_changes_need_the_csrf_token(client: TestClient) -> None:
    csrf = register(client)
    site = create_site(client, csrf)
    url = f"/api/sites/{site['id']}"

    assert client.post("/api/sites", json=SITE).status_code == 403
    assert client.post("/api/sites", json=SITE, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.put(url, json=SITE).status_code == 403
    assert client.delete(url).status_code == 403
    assert client.get(url).status_code == 200  # reading needs no token
    assert len(client.get("/api/sites").json()) == 1  # nothing was created or deleted


def test_advisors_only_see_their_own_sites(client: TestClient, other_client: TestClient) -> None:
    site = create_site(client, register(client, "anna@example.com"))
    other_csrf = register(other_client, "bram@example.com")
    headers = {"X-CSRF-Token": other_csrf}
    url = f"/api/sites/{site['id']}"

    assert other_client.get("/api/sites").json() == []
    # Not "403 Forbidden": the same 404 as for a site that does not exist,
    # so Bram cannot even find out that site exists.
    assert other_client.get(url).status_code == 404
    assert other_client.put(url, json=SITE, headers=headers).status_code == 404
    assert other_client.delete(url, headers=headers).status_code == 404
    assert other_client.get(f"{url}/production").status_code == 404
    assert other_client.get(f"{url}/battery?capacityKwh=5&annualUseKwh=3000").status_code == 404

    assert client.get(url).json() == site  # untouched


def test_the_owner_and_id_cannot_be_set_from_the_body(client: TestClient, other_client: TestClient) -> None:
    site = create_site(client, register(client, "anna@example.com"))
    other_csrf = register(other_client, "bram@example.com")
    sneaky = {**SITE, "id": site["id"], "userId": 1, "clientName": "Overwrite attempt"}

    response = other_client.post("/api/sites", json=sneaky, headers={"X-CSRF-Token": other_csrf})
    assert response.status_code == 201
    assert response.json()["id"] != site["id"]
    assert client.get(f"/api/sites/{site['id']}").json() == site
    assert len(client.get("/api/sites").json()) == 1


def test_invalid_sites_get_a_message_per_field(client: TestClient) -> None:
    csrf = register(client)
    bad = {"clientName": "   ", "latitude": 91, "longitude": "4.3", "roofAreaM2": -1, "peakKwp": 0}
    errors = errors_of(client.post("/api/sites", json=bad, headers={"X-CSRF-Token": csrf}))
    assert errors == {
        "clientName": "This field is required.",
        "address": "This field is required.",
        "latitude": "Must be at most 90.",
        "longitude": "Must be a number.",
        "roofAreaM2": "Must be greater than 0.",
        "peakKwp": "Must be greater than 0.",
    }


def test_numbers_must_be_real_numbers(client: TestClient) -> None:
    csrf = register(client)
    headers = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    errors = errors_of(client.post("/api/sites", json={**SITE, "latitude": True}, headers=headers))
    assert errors == {"latitude": "Must be a number."}
    body = '{"clientName": "A", "address": "B", "latitude": NaN, "longitude": Infinity, "peakKwp": 5}'
    errors = errors_of(client.post("/api/sites", content=body, headers=headers))
    assert errors == {"latitude": "Must be a finite number.", "longitude": "Must be a finite number."}


def test_snake_case_field_names_are_not_accepted(client: TestClient) -> None:
    csrf = register(client)
    snake = {**SITE, "client_name": "A"}
    del snake["clientName"]
    errors = errors_of(client.post("/api/sites", json=snake, headers={"X-CSRF-Token": csrf}))
    assert errors == {"clientName": "This field is required."}


def test_broken_json_is_a_clear_422(client: TestClient) -> None:
    csrf = register(client)
    headers = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    errors = errors_of(client.post("/api/sites", content="{not json", headers=headers))
    assert errors == {"body": "The request body is not valid JSON."}
    errors = errors_of(client.post("/api/sites", json=[1, 2], headers=headers))
    assert errors == {"body": "Expected a JSON object."}


def test_odd_ids(client: TestClient) -> None:
    register(client)
    assert client.get("/api/sites/0").status_code == 404
    assert client.get("/api/sites/-5").status_code == 404
    assert client.get("/api/sites/99999999999999999999999999").status_code == 404  # not a 500
    assert client.get("/api/sites/abc").status_code == 422


def test_ids_of_deleted_sites_are_not_reused(client: TestClient) -> None:
    csrf = register(client)
    first = create_site(client, csrf)
    client.delete(f"/api/sites/{first['id']}", headers={"X-CSRF-Token": csrf})
    second = create_site(client, csrf)
    assert second["id"] > first["id"]
