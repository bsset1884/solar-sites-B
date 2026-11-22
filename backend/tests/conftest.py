"""Shared test setup: a fresh app per test with its own database and a fake PVGIS."""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings
from app.main import create_app
from app.pvgis import HourlySeries, MonthlyEstimate, PvgisError

# Real PVcalc answer for Den Haag (52.08, 4.31) with 5 kWp, optimal angles.
MONTHLY_KWH_5KWP = (191.62, 280.9, 487.92, 639.89, 677.02, 657.8,
                    647.81, 587.43, 483.2, 336.72, 202.07, 148.59)  # fmt: skip
YEARLY_KWH_5KWP = 5340.96

SITE = {
    "clientName": "Familie Jansen",
    "address": "Laan van Meerdervoort 1, Den Haag",
    "latitude": 52.08,
    "longitude": 4.31,
    "roofAreaM2": 40,
    "peakKwp": 5,
}


def synthetic_hourly(peak_kwp: float) -> HourlySeries:
    """A smooth sunny-day curve for 2023 (UTC), longer and stronger in summer.
    Not real weather, but realistic enough to test the logic."""
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    times, kwh = [], []
    for hour in range(8760):
        time = start + timedelta(hours=hour)
        day = time.timetuple().tm_yday
        season = 0.5 - 0.5 * math.cos(2 * math.pi * (day - 10) / 365)  # 0 in January, 1 in July
        day_length = 8 + 8 * season
        from_noon = time.hour + 0.5 - 11.7  # solar noon in Den Haag is about 11:42 UTC
        sun = math.cos(math.pi * from_noon / day_length) if abs(from_noon) < day_length / 2 else 0.0
        times.append(time)
        kwh.append(peak_kwp * (0.2 + 0.6 * season) * sun)
    return HourlySeries(times_utc=tuple(times), kwh=tuple(kwh))


class FakePvgis:
    """Stands in for PvgisClient, so tests never call the real API."""

    def __init__(self) -> None:
        self.error: PvgisError | None = None  # set this to make every call fail

    def monthly(self, lat: float, lon: float, peak_kwp: float) -> MonthlyEstimate:
        if self.error:
            raise self.error
        factor = peak_kwp / 5
        return MonthlyEstimate(
            yearly_kwh=YEARLY_KWH_5KWP * factor,
            monthly_kwh=tuple(kwh * factor for kwh in MONTHLY_KWH_5KWP),
        )

    def hourly(self, lat: float, lon: float, peak_kwp: float) -> HourlySeries:
        if self.error:
            raise self.error
        return synthetic_hourly(peak_kwp)

    def close(self) -> None:
        pass


def make_settings(tmp_path: Path, **changes) -> Settings:
    values = {
        "data_dir": tmp_path / "data",
        "static_dir": tmp_path / "static",
        "pvgis_base_url": "https://pvgis.invalid/api",
        "pvgis_timeout_seconds": 1.0,
        "session_ttl_seconds": 3600,
        "cookie_secure": False,
        "login_max_failures": 10,
        "login_window_seconds": 900,
    }
    return Settings(**{**values, **changes})


@pytest.fixture
def fake_pvgis() -> FakePvgis:
    return FakePvgis()


@pytest.fixture
def app(tmp_path: Path, fake_pvgis: FakePvgis) -> FastAPI:
    return create_app(make_settings(tmp_path), pvgis=fake_pvgis)


@pytest.fixture
def client(app: FastAPI):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def other_client(app: FastAPI):
    """A second browser (its own cookies) on the same app: another advisor."""
    with TestClient(app) as test_client:
        yield test_client


def register(client: TestClient, email: str = "advisor@example.com", password: str = "correct horse") -> str:
    response = client.post("/api/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()["csrfToken"]


def create_site(client: TestClient, csrf: str, **changes) -> dict:
    response = client.post("/api/sites", json={**SITE, **changes}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201, response.text
    return response.json()


def errors_of(response: Response) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return response.json()["errors"]
