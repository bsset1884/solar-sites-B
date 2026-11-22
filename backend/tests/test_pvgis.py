"""The real PvgisClient against a fake HTTP transport (no network needed)."""

from datetime import datetime, timezone

import httpx
import pytest

from app.pvgis import PvgisClient, PvgisError

from .conftest import MONTHLY_KWH_5KWP, YEARLY_KWH_5KWP

# The shape of a real PVcalc answer (trimmed to the parts we read).
PVCALC_ANSWER = {
    "inputs": {"location": {"latitude": 52.08, "longitude": 4.31}},
    "outputs": {
        "monthly": {
            "fixed": [
                {"month": month, "E_d": 0, "E_m": kwh, "H(i)_d": 0, "H(i)_m": 0, "SD_m": 0}
                for month, kwh in enumerate(MONTHLY_KWH_5KWP, start=1)
            ]
        },
        "totals": {"fixed": {"E_d": 14.63, "E_m": 445.08, "E_y": YEARLY_KWH_5KWP, "SD_y": 246.46}},
    },
    "meta": {},
}

SEA = {"message": "Location over the sea. Please, select another location", "status": 400}


def pvgis_with(handler) -> PvgisClient:
    return PvgisClient("https://pvgis.test/api/v5_3", 5.0, transport=httpx.MockTransport(handler))


def test_monthly_reads_pvcalc_and_caches_it() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=PVCALC_ANSWER)

    pvgis = pvgis_with(handler)
    estimate = pvgis.monthly(52.08, 4.31, 5.0)
    assert estimate.yearly_kwh == YEARLY_KWH_5KWP
    assert estimate.monthly_kwh == MONTHLY_KWH_5KWP

    request = requests[0]
    assert request.url.path == "/api/v5_3/PVcalc"
    assert dict(request.url.params) == {
        "lat": "52.08",
        "lon": "4.31",
        "peakpower": "5.0",
        "loss": "14",
        "optimalangles": "1",
        "outputformat": "json",
    }

    pvgis.monthly(52.08, 4.31, 5.0)
    assert len(requests) == 1  # the second time comes from the cache


def test_hourly_reads_seriescalc() -> None:
    answer = {
        "outputs": {
            "hourly": [
                {"time": "20230101:0011", "P": 0.0, "G(i)": 0.0},
                {"time": "20230701:1211", "P": 2500.0, "G(i)": 800.0},
                {"time": "20230701:1311", "P": -0.4, "G(i)": 0.0},  # tiny negative values happen
            ]
        }
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=answer)

    series = pvgis_with(handler).hourly(52.08, 4.31, 5.0)
    assert series.times_utc[1] == datetime(2023, 7, 1, 12, 11, tzinfo=timezone.utc)
    assert series.kwh == (0.0, 2.5, 0.0)  # watts during one hour -> kWh
    params = requests[0].url.params
    assert requests[0].url.path == "/api/v5_3/seriescalc"
    assert (params["pvcalculation"], params["startyear"], params["endyear"]) == ("1", "2023", "2023")
    assert params["optimalangles"] == "1"


def test_location_without_data_is_a_clear_422() -> None:
    pvgis = pvgis_with(lambda request: httpx.Response(400, json=SEA))
    with pytest.raises(PvgisError) as error:
        pvgis.monthly(54.0, -20.0, 5.0)
    assert error.value.status_code == 422
    assert error.value.message == (
        "PVGIS cannot give an estimate for this location: "
        "Location over the sea. Please, select another location"
    )


def test_failures_are_not_cached() -> None:
    answers = [httpx.Response(529), httpx.Response(200, json=PVCALC_ANSWER)]
    pvgis = pvgis_with(lambda request: answers.pop(0))
    with pytest.raises(PvgisError):
        pvgis.monthly(52.08, 4.31, 5.0)
    assert pvgis.monthly(52.08, 4.31, 5.0).yearly_kwh == YEARLY_KWH_5KWP


@pytest.mark.parametrize(
    ("pvgis_status", "our_status"),
    [(429, 503), (529, 503), (500, 502), (503, 502), (404, 502)],
)
def test_pvgis_errors_become_gateway_errors(pvgis_status: int, our_status: int) -> None:
    pvgis = pvgis_with(lambda request: httpx.Response(pvgis_status, text="error"))
    with pytest.raises(PvgisError) as error:
        pvgis.monthly(52.08, 4.31, 5.0)
    assert error.value.status_code == our_status


def test_timeout_is_504_and_network_error_is_502() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(PvgisError) as error:
        pvgis_with(timeout).monthly(52.08, 4.31, 5.0)
    assert error.value.status_code == 504
    with pytest.raises(PvgisError) as error:
        pvgis_with(unreachable).monthly(52.08, 4.31, 5.0)
    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, json={"outputs": {}}),
        httpx.Response(200, json=[1, 2, 3]),
    ],
)
def test_unreadable_answers_are_502(response: httpx.Response) -> None:
    with pytest.raises(PvgisError) as error:
        pvgis_with(lambda request: response).monthly(52.08, 4.31, 5.0)
    assert error.value.status_code == 502
