import pytest
from fastapi.testclient import TestClient

from app.pvgis import PvgisError

from .conftest import FakePvgis, create_site, register


def test_production_follows_the_contract(client: TestClient) -> None:
    site = create_site(client, register(client))
    response = client.get(f"/api/sites/{site['id']}/production")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"yearlyKwh", "monthlyKwh"}
    assert body["yearlyKwh"] == 5341.0
    assert [month["month"] for month in body["monthlyKwh"]] == list(range(1, 13))
    assert body["monthlyKwh"][0] == {"month": 1, "kwh": 191.6}


def test_production_scales_with_the_panels(client: TestClient) -> None:
    site = create_site(client, register(client), peakKwp=10)
    body = client.get(f"/api/sites/{site['id']}/production").json()
    assert body["yearlyKwh"] == pytest.approx(2 * 5340.96, abs=0.1)


@pytest.mark.parametrize("status", [422, 502, 503, 504])
def test_pvgis_problems_are_passed_on_clearly(client: TestClient, fake_pvgis: FakePvgis, status: int) -> None:
    site = create_site(client, register(client), latitude=54.0, longitude=-20.0)
    fake_pvgis.error = PvgisError("PVGIS cannot give an estimate for this location: over the sea", status)
    for path in ("production", "battery?capacityKwh=5&annualUseKwh=3000"):
        response = client.get(f"/api/sites/{site['id']}/{path}")
        assert response.status_code == status
        assert response.json() == {
            "detail": "PVGIS cannot give an estimate for this location: over the sea"
        }
