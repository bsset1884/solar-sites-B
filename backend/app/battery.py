"""How much solar energy a household uses itself, with and without a home battery.

PVGIS gives the production per hour. The household's use is not known, so we
model it (see README, "Household electricity use"): the advisor enters the
yearly use, and we spread it over the 8,760 hours of the year with a typical
household pattern. Then we step through the year hour by hour.

Only pure functions here (no database, no HTTP), so it is easy to test.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tzfpy import get_tz

# Relative use per hour of the day (local clock time), 0:00 first. A typical
# household: a low base load at night (fridge, standby), a bump in the morning
# and a peak around dinner time, when the sun is already low.
HOURLY_PROFILE = (
    0.70, 0.55, 0.50, 0.48, 0.48, 0.52,  # 00-05 night
    0.65, 0.90, 1.00, 0.95, 0.90, 0.90,  # 06-11 morning
    0.95, 0.90, 0.85, 0.90, 1.05, 1.40,  # 12-17 afternoon
    1.75, 1.70, 1.55, 1.40, 1.20, 0.95,  # 18-23 evening peak
)  # fmt: skip

# Relative use per month, January first: more light and more time indoors in
# winter, so about 40% more use than in summer.
MONTHLY_PROFILE = (1.20, 1.10, 1.05, 0.95, 0.90, 0.85, 0.85, 0.85, 0.90, 1.00, 1.10, 1.25)

ROUND_TRIP_EFFICIENCY = 0.90  # 10% of the energy put in is lost (typical lithium battery)
MAX_POWER_PER_KWH = 0.5  # a 10 kWh battery charges/discharges at most 5 kW (0.5C)


@dataclass(frozen=True)
class ScenarioResult:
    self_used_kwh: float
    grid_export_kwh: float
    grid_import_kwh: float
    self_consumption_pct: float  # self-used / production
    self_sufficiency_pct: float  # self-used / consumption


@dataclass(frozen=True)
class BatteryReport:
    production_kwh: float
    consumption_kwh: float
    without_battery: ScenarioResult
    with_battery: ScenarioResult


def local_timezone(lat: float, lon: float) -> ZoneInfo:
    """Time zone at a location, e.g. Europe/Amsterdam (with summer time)."""
    name = get_tz(lon, lat)  # note: tzfpy wants longitude first
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def scale_to_total(values: Sequence[float], total: float) -> list[float]:
    """Scale values so that they add up to total (keeps the shape)."""
    current = sum(values)
    if current <= 0:
        return list(values)
    factor = total / current
    return [value * factor for value in values]


def household_load(times_utc: Sequence[datetime], annual_use_kwh: float, tz: ZoneInfo) -> list[float]:
    """Electricity use in each hour; the hours add up to annual_use_kwh."""
    weights = []
    for time_utc in times_utc:
        local = time_utc.astimezone(tz)  # people live by the local clock, PVGIS uses UTC
        weights.append(HOURLY_PROFILE[local.hour] * MONTHLY_PROFILE[local.month - 1])
    return scale_to_total(weights, annual_use_kwh)


def simulate(
    production: Sequence[float], load: Sequence[float], capacity_kwh: float
) -> tuple[float, float, float]:
    """Step through the year hour by hour.

    Each hour, the house first uses solar power directly. Solar power that is
    left over charges the battery (export to the grid when it is full). Use
    that is not covered comes from the battery, and then from the grid.

    Returns (self_used_kwh, grid_export_kwh, grid_import_kwh).
    """
    charge_efficiency = discharge_efficiency = math.sqrt(ROUND_TRIP_EFFICIENCY)
    max_energy_per_hour = capacity_kwh * MAX_POWER_PER_KWH
    stored = 0.0  # kWh in the battery; it starts empty on 1 January
    self_used = exported = imported = 0.0

    for solar, use in zip(production, load, strict=True):
        direct = min(solar, use)
        surplus = solar - direct  # at most one of these two is above zero
        shortage = use - direct

        # Charge with the surplus: limited by power and by the free space.
        charged = min(surplus, max_energy_per_hour, (capacity_kwh - stored) / charge_efficiency)
        stored += charged * charge_efficiency

        # Discharge for the shortage: limited by power and by what is stored.
        delivered = min(shortage, max_energy_per_hour, stored * discharge_efficiency)
        stored -= delivered / discharge_efficiency

        self_used += direct + delivered
        exported += surplus - charged
        imported += shortage - delivered

    return self_used, exported, imported


def _percent(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole > 0 else 0.0


def battery_report(production: Sequence[float], load: Sequence[float], capacity_kwh: float) -> BatteryReport:
    total_production = sum(production)
    total_use = sum(load)

    def scenario(capacity: float) -> ScenarioResult:
        self_used, exported, imported = simulate(production, load, capacity)
        return ScenarioResult(
            self_used_kwh=round(self_used, 1),
            grid_export_kwh=round(exported, 1),
            grid_import_kwh=round(imported, 1),
            self_consumption_pct=_percent(self_used, total_production),
            self_sufficiency_pct=_percent(self_used, total_use),
        )

    return BatteryReport(
        production_kwh=round(total_production, 1),
        consumption_kwh=round(total_use, 1),
        without_battery=scenario(0.0),
        with_battery=scenario(capacity_kwh),
    )
