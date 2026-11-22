"""Client for PVGIS, the free solar API of the European Commission (JRC).

All PVGIS calls go through here, on the server. (PVGIS also refuses calls
straight from a browser: it sends no CORS headers.)
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

SYSTEM_LOSS_PCT = 14  # losses in cables, inverter and dirt; the value PVGIS suggests
SERIES_YEAR = 2023  # latest full year in PVGIS 5.3 (SARAH3 and ERA5 cover 2005-2023)


class PvgisError(Exception):
    """Something went wrong with PVGIS; carries the HTTP status we answer with."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class MonthlyEstimate:
    yearly_kwh: float  # long-term average (all years PVGIS has)
    monthly_kwh: tuple[float, ...]  # 12 values, January first


@dataclass(frozen=True)
class HourlySeries:
    times_utc: tuple[datetime, ...]  # PVGIS times are in UTC
    kwh: tuple[float, ...]  # energy produced in each hour


class _LruCache:
    """A small thread-safe cache that forgets the least recently used entry."""

    def __init__(self, max_items: int) -> None:
        self._items: OrderedDict[Any, Any] = OrderedDict()
        self._max_items = max_items
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            if len(self._items) > self._max_items:
                self._items.popitem(last=False)


class PvgisClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,  # tests pass a fake transport
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            headers={"User-Agent": "praeter-solar-sites/1.0"},
            transport=transport,
        )
        # PVGIS results for a location never change, so we keep them. This makes
        # the app fast and keeps us far below the PVGIS limit of 30 calls/second.
        self._monthly_cache = _LruCache(max_items=256)
        self._hourly_cache = _LruCache(max_items=32)  # ~8760 values each

    def close(self) -> None:
        self._http.close()

    def monthly(self, lat: float, lon: float, peak_kwp: float) -> MonthlyEstimate:
        """Average yearly and monthly production (PVcalc), panels at the optimal angle."""
        key = (lat, lon, peak_kwp)
        cached = self._monthly_cache.get(key)
        if cached is not None:
            return cached

        data = self._get(
            "PVcalc",
            {
                "lat": lat,
                "lon": lon,
                "peakpower": peak_kwp,
                "loss": SYSTEM_LOSS_PCT,
                "optimalangles": 1,
                "outputformat": "json",
            },
        )
        try:
            months = sorted(data["outputs"]["monthly"]["fixed"], key=lambda m: int(m["month"]))
            estimate = MonthlyEstimate(
                yearly_kwh=float(data["outputs"]["totals"]["fixed"]["E_y"]),
                monthly_kwh=tuple(float(m["E_m"]) for m in months),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PvgisError("PVGIS sent an answer we could not read.", 502) from exc
        if len(estimate.monthly_kwh) != 12:
            raise PvgisError("PVGIS sent an answer we could not read.", 502)

        self._monthly_cache.put(key, estimate)
        return estimate

    def hourly(self, lat: float, lon: float, peak_kwp: float) -> HourlySeries:
        """Production per hour for one real year (seriescalc), same panel setup."""
        key = (lat, lon, peak_kwp)
        cached = self._hourly_cache.get(key)
        if cached is not None:
            return cached

        data = self._get(
            "seriescalc",
            {
                "lat": lat,
                "lon": lon,
                "peakpower": peak_kwp,
                "loss": SYSTEM_LOSS_PCT,
                "pvcalculation": 1,
                "optimalangles": 1,
                "startyear": SERIES_YEAR,
                "endyear": SERIES_YEAR,
                "outputformat": "json",
            },
        )
        try:
            rows = data["outputs"]["hourly"]
            series = HourlySeries(
                # "20230101:0011" = 1 January 2023, the hour starting 00:00 UTC
                times_utc=tuple(
                    datetime.strptime(row["time"], "%Y%m%d:%H%M").replace(tzinfo=timezone.utc)
                    for row in rows
                ),
                # P is the average power in watts during that hour, so P Wh = P/1000 kWh.
                kwh=tuple(max(float(row["P"]), 0.0) / 1000 for row in rows),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PvgisError("PVGIS sent an answer we could not read.", 502) from exc
        if not series.kwh:
            raise PvgisError("PVGIS sent an answer we could not read.", 502)

        self._hourly_cache.put(key, series)
        return series

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """One GET to PVGIS, with every failure turned into a PvgisError."""
        try:
            response = self._http.get(endpoint, params=params)
        except httpx.TimeoutException as exc:
            raise PvgisError("PVGIS did not answer in time. Please try again.", 504) from exc
        except httpx.HTTPError as exc:
            raise PvgisError("Could not reach PVGIS. Please try again later.", 502) from exc

        if response.status_code == 400:
            # PVGIS answers 400 with a reason, e.g. "Location over the sea. Please,
            # select another location". That is about the site, not a server fault.
            raise PvgisError(
                f"PVGIS cannot give an estimate for this location: {_reason(response)}", 422
            )
        if response.status_code in (429, 529):  # too many requests / overloaded
            raise PvgisError("PVGIS is busy right now. Please try again in a moment.", 503)
        if response.status_code != 200:
            raise PvgisError(f"PVGIS returned an error (HTTP {response.status_code}).", 502)
        try:
            data = response.json()
        except ValueError as exc:
            raise PvgisError("PVGIS sent an answer we could not read.", 502) from exc
        if not isinstance(data, dict):
            raise PvgisError("PVGIS sent an answer we could not read.", 502)
        return data


def _reason(response: httpx.Response) -> str:
    try:
        message = str(response.json()["message"])
    except (ValueError, KeyError, TypeError):
        return "no details given."
    return message[:200]
