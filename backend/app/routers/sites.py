"""Client sites (create, read, update, delete) and their production and battery analysis."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select

from ..battery import battery_report, household_load, local_timezone, scale_to_total
from ..db import DbSession
from ..models import Site
from ..pvgis import PvgisClient
from ..schemas import BatteryOut, ErrorOut, ProductionOut, SiteIn, SiteOut, ValidationErrorOut
from ..security import CurrentUser

router = APIRouter(
    prefix="/api/sites",
    tags=["sites"],
    responses={401: {"model": ErrorOut}, 422: {"model": ValidationErrorOut}},
)

MAX_SQLITE_INTEGER = 2**63 - 1


def get_own_site(site_id: int, user: CurrentUser, db: DbSession) -> Site:
    """The site, but only if it belongs to the logged-in advisor.

    Another advisor's site gets the same 404 as a site that does not exist, so
    nobody can find out which ids exist. (403 would confirm that it exists.)
    """
    if not 0 < site_id <= MAX_SQLITE_INTEGER:  # SQLite integers are 64-bit
        raise HTTPException(status_code=404, detail="Site not found.")
    site = db.scalar(select(Site).where(Site.id == site_id, Site.user_id == user.id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found.")
    return site


OwnSite = Annotated[Site, Depends(get_own_site)]


def get_pvgis(request: Request) -> PvgisClient:
    return request.app.state.pvgis


Pvgis = Annotated[PvgisClient, Depends(get_pvgis)]

NOT_FOUND = {404: {"model": ErrorOut}}
PVGIS_ERRORS = {
    404: {"model": ErrorOut},
    502: {"model": ErrorOut, "description": "PVGIS failed"},
    503: {"model": ErrorOut, "description": "PVGIS is busy"},
    504: {"model": ErrorOut, "description": "PVGIS timed out"},
}


@router.get("", response_model=list[SiteOut])
def list_sites(user: CurrentUser, db: DbSession) -> list[Site]:
    return list(db.scalars(select(Site).where(Site.user_id == user.id).order_by(Site.id)))


@router.post("", status_code=201, response_model=SiteOut, responses={403: {"model": ErrorOut}})
def create_site(body: SiteIn, user: CurrentUser, db: DbSession, response: Response) -> Site:
    # The owner always comes from the session, never from the request body.
    site = Site(user_id=user.id, **body.model_dump())
    db.add(site)
    db.commit()
    response.headers["Location"] = f"/api/sites/{site.id}"
    return site


@router.get("/{site_id}", response_model=SiteOut, responses=NOT_FOUND)
def get_site(site: OwnSite) -> Site:
    return site


@router.put("/{site_id}", response_model=SiteOut, responses=NOT_FOUND)
def update_site(body: SiteIn, site: OwnSite, db: DbSession) -> Site:
    # PUT replaces the whole site, so a missing roofAreaM2 becomes empty.
    for field, value in body.model_dump().items():
        setattr(site, field, value)
    db.commit()
    return site


@router.delete("/{site_id}", status_code=204, responses=NOT_FOUND)
def delete_site(site: OwnSite, db: DbSession) -> None:
    db.delete(site)
    db.commit()


@router.get("/{site_id}/production", response_model=ProductionOut, responses=PVGIS_ERRORS)
def get_production(site: OwnSite, pvgis: Pvgis) -> dict[str, Any]:
    estimate = pvgis.monthly(site.latitude, site.longitude, site.peak_kwp)
    return {
        "yearly_kwh": round(estimate.yearly_kwh, 1),
        "monthly_kwh": [
            {"month": month, "kwh": round(kwh, 1)}
            for month, kwh in enumerate(estimate.monthly_kwh, start=1)
        ],
    }


@router.get("/{site_id}/battery", response_model=BatteryOut, responses=PVGIS_ERRORS)
def get_battery(
    site: OwnSite,
    pvgis: Pvgis,
    capacity_kwh: Annotated[float, Query(alias="capacityKwh", ge=0, le=1_000, allow_inf_nan=False)],
    annual_use_kwh: Annotated[
        float, Query(alias="annualUseKwh", gt=0, le=1_000_000, allow_inf_nan=False)
    ],
) -> dict[str, Any]:
    estimate = pvgis.monthly(site.latitude, site.longitude, site.peak_kwp)
    series = pvgis.hourly(site.latitude, site.longitude, site.peak_kwp)
    # The hourly pattern of one real year, scaled to the long-term average total,
    # so this answer and /production show the same yearly production.
    production = scale_to_total(series.kwh, estimate.yearly_kwh)
    load = household_load(
        series.times_utc, annual_use_kwh, local_timezone(site.latitude, site.longitude)
    )
    return asdict(battery_report(production, load, capacity_kwh))
