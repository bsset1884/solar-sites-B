"""Request and response bodies (Pydantic).

JSON uses camelCase (clientName) as the API contract asks; Python uses
snake_case (client_name). The alias generator converts between the two.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,  # lets our own code write AuthOut(csrf_token=...)
        allow_inf_nan=False,  # NaN and Infinity are not valid numbers for us
    )


class InputModel(ApiModel):
    # Clients must use the camelCase names from the contract.
    model_config = ConfigDict(validate_by_name=False)


# ---------- auth ----------

# Deliberately simple: one "@", no spaces, a dot in the domain. Real proof that
# an address exists would be a confirmation email, which is out of scope.
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class RegisterIn(InputModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginIn(InputModel):
    # No password rules here: a wrong password must simply give 401.
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthOut(ApiModel):
    email: str
    csrf_token: str  # send back in the X-CSRF-Token header on POST/PUT/DELETE


# ---------- sites ----------


class SiteIn(InputModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    client_name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=300)
    # strict=True: only real JSON numbers, so true or "52" is rejected.
    latitude: float = Field(strict=True, ge=-90, le=90)
    longitude: float = Field(strict=True, ge=-180, le=180)
    roof_area_m2: float | None = Field(default=None, strict=True, gt=0, le=100_000)
    peak_kwp: float = Field(strict=True, gt=0, le=1_000)


class SiteOut(ApiModel):
    model_config = ConfigDict(from_attributes=True)  # build it from a Site row

    id: int
    client_name: str
    address: str
    latitude: float
    longitude: float
    roof_area_m2: float | None
    peak_kwp: float


# ---------- production and battery ----------


class MonthKwh(ApiModel):
    month: int  # 1 = January
    kwh: float


class ProductionOut(ApiModel):
    yearly_kwh: float
    monthly_kwh: list[MonthKwh]


class Scenario(ApiModel):
    self_used_kwh: float  # solar energy the household uses itself (directly or via the battery)
    grid_export_kwh: float  # solar energy that goes to the grid
    grid_import_kwh: float  # energy still bought from the grid
    self_consumption_pct: float  # share of the solar production used at home
    self_sufficiency_pct: float  # share of the household's use covered by solar


class BatteryOut(ApiModel):
    production_kwh: float
    consumption_kwh: float
    without_battery: Scenario
    with_battery: Scenario


# ---------- errors (for the OpenAPI docs) ----------


class ErrorOut(BaseModel):
    detail: str


class ValidationErrorOut(BaseModel):
    detail: str
    errors: dict[str, str]  # field name -> message
