from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.battery import (
    HOURLY_PROFILE,
    household_load,
    local_timezone,
    scale_to_total,
    simulate,
)

from .conftest import create_site, errors_of, register, synthetic_hourly

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
UTC = timezone.utc
YEAR_2023 = [datetime(2023, 1, 1, tzinfo=UTC) + timedelta(hours=hour) for hour in range(8760)]


def test_time_zone_comes_from_the_location() -> None:
    assert local_timezone(52.08, 4.31).key == "Europe/Amsterdam"
    assert local_timezone(40.0, -100.0).key == "America/Chicago"


def test_household_load_adds_up_to_the_yearly_use() -> None:
    load = household_load(YEAR_2023, 3500, AMSTERDAM)
    assert len(load) == 8760
    assert sum(load) == pytest.approx(3500)
    winter_day = sum(load[14 * 24 : 15 * 24])  # 15 January
    summer_day = sum(load[195 * 24 : 196 * 24])  # 15 July
    assert winter_day > 1.3 * summer_day


def test_household_load_follows_the_local_clock_with_summer_time() -> None:
    # 19:00 in Den Haag is 18:00 UTC in winter but 17:00 UTC in summer.
    winter = household_load(
        [datetime(2023, 1, 10, 18, tzinfo=UTC), datetime(2023, 1, 10, 2, tzinfo=UTC)], 1, AMSTERDAM
    )
    summer = household_load(
        [datetime(2023, 7, 10, 17, tzinfo=UTC), datetime(2023, 7, 10, 1, tzinfo=UTC)], 1, AMSTERDAM
    )
    evening_vs_night = HOURLY_PROFILE[19] / HOURLY_PROFILE[3]
    assert winter[0] / winter[1] == pytest.approx(evening_vs_night)
    assert summer[0] / summer[1] == pytest.approx(evening_vs_night)


def test_scale_to_total_keeps_the_shape() -> None:
    assert scale_to_total([1, 3], 8) == [2, 6]
    assert scale_to_total([0, 0], 8) == [0, 0]


def test_without_battery_only_direct_use_counts() -> None:
    # Hour 1: no sun. Hour 2: 3 kWh sun, 1 kWh used. Hour 3: no sun.
    assert simulate([0, 3, 0], [1, 1, 1], capacity_kwh=0) == (1, 2, 2)


def test_the_battery_moves_the_surplus_to_later() -> None:
    self_used, exported, imported = simulate([0, 3, 0], [1, 1, 1], capacity_kwh=10)
    # The 2 kWh surplus of hour 2 is stored and covers the 1 kWh of hour 3.
    assert self_used == pytest.approx(2)
    assert exported == pytest.approx(0)
    assert imported == pytest.approx(1)


def test_the_battery_loses_energy_and_has_a_power_limit() -> None:
    # 4 kWh battery -> at most 2 kWh per hour in or out.
    self_used, exported, imported = simulate([10, 0], [0, 10], capacity_kwh=4)
    assert exported == pytest.approx(8)  # only 2 kWh could go in
    assert self_used == pytest.approx(1.8)  # 90% of it comes back out
    assert imported == pytest.approx(8.2)


def test_the_battery_never_holds_more_than_its_capacity() -> None:
    # Three very sunny hours fill a 5 kWh battery (2.5 kWh per hour at most);
    # afterwards it can give back what fits in it, minus the discharge loss.
    production = [100, 100, 100] + [0] * 20
    load = [0, 0, 0] + [1] * 20
    self_used, exported, _ = simulate(production, load, capacity_kwh=5)
    assert self_used == pytest.approx(5 * 0.9**0.5)
    assert exported == pytest.approx(300 - 5 / 0.9**0.5)


def test_sanity_over_a_whole_year() -> None:
    production = list(synthetic_hourly(5).kwh)
    load = household_load(YEAR_2023, 3500, AMSTERDAM)
    total_production, total_use = sum(production), sum(load)

    without = simulate(production, load, 0)
    small = simulate(production, load, 5)
    large = simulate(production, load, 15)
    for self_used, exported, imported in (without, small, large):
        assert self_used + imported == pytest.approx(total_use)  # every kWh used came from somewhere
        assert self_used + exported <= total_production + 1e-6  # no energy from nothing
    assert without[0] < small[0] < large[0] <= min(total_production, total_use)
    assert without[1] > small[1] > large[1]  # less export as the battery grows


def test_battery_endpoint_follows_the_contract(client: TestClient) -> None:
    site = create_site(client, register(client))
    response = client.get(
        f"/api/sites/{site['id']}/battery", params={"capacityKwh": 10, "annualUseKwh": 3500}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"productionKwh", "consumptionKwh", "withoutBattery", "withBattery"}
    assert body["productionKwh"] == 5341.0  # the same yearly total as /production
    assert body["consumptionKwh"] == 3500
    scenario_keys = {
        "selfUsedKwh",
        "gridExportKwh",
        "gridImportKwh",
        "selfConsumptionPct",
        "selfSufficiencyPct",
    }
    assert set(body["withoutBattery"]) == scenario_keys == set(body["withBattery"])
    assert body["withBattery"]["selfUsedKwh"] > body["withoutBattery"]["selfUsedKwh"]
    without = body["withoutBattery"]
    assert without["selfConsumptionPct"] == pytest.approx(
        100 * without["selfUsedKwh"] / body["productionKwh"], abs=0.1
    )


def test_a_zero_kwh_battery_adds_nothing(client: TestClient) -> None:
    site = create_site(client, register(client))
    body = client.get(
        f"/api/sites/{site['id']}/battery", params={"capacityKwh": 0, "annualUseKwh": 3500}
    ).json()
    assert body["withBattery"] == body["withoutBattery"]


def test_battery_parameters_are_validated(client: TestClient) -> None:
    site = create_site(client, register(client))
    url = f"/api/sites/{site['id']}/battery"
    assert errors_of(client.get(url)) == {
        "capacityKwh": "This field is required.",
        "annualUseKwh": "This field is required.",
    }
    assert errors_of(client.get(url, params={"capacityKwh": -1, "annualUseKwh": 0})) == {
        "capacityKwh": "Must be at least 0.",
        "annualUseKwh": "Must be greater than 0.",
    }
    assert errors_of(client.get(url, params={"capacityKwh": "nan", "annualUseKwh": "lots"})) == {
        "capacityKwh": "Must be a finite number.",
        "annualUseKwh": "Must be a number.",
    }
