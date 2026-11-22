"""Turns errors into clear JSON answers."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .pvgis import PvgisError


def _number(value: float) -> str:
    """90.0 -> "90", 0.5 -> "0.5", 100000 -> "100,000"."""
    value = float(value)
    return f"{value:,.0f}" if value.is_integer() else f"{value:,}"


def _message(error: dict) -> str:
    """A short, human message for one Pydantic validation error."""
    kind = error["type"]
    ctx = error.get("ctx") or {}
    if kind == "missing":
        return "This field is required."
    if kind == "string_too_short":
        if ctx.get("min_length") == 1:
            return "This field is required."
        return f"Must be at least {ctx['min_length']} characters."
    if kind == "string_too_long":
        return f"Must be at most {ctx['max_length']} characters."
    if kind == "string_type":
        return "Must be text."
    if kind in ("float_type", "float_parsing", "int_type", "int_parsing"):
        return "Must be a number."
    if kind == "finite_number":
        return "Must be a finite number."
    if kind == "greater_than_equal":
        return f"Must be at least {_number(ctx['ge'])}."
    if kind == "greater_than":
        return f"Must be greater than {_number(ctx['gt'])}."
    if kind == "less_than_equal":
        return f"Must be at most {_number(ctx['le'])}."
    if kind == "less_than":
        return f"Must be less than {_number(ctx['lt'])}."
    if kind == "value_error":
        return str(ctx.get("error", error["msg"]))
    if kind == "json_invalid":
        return "The request body is not valid JSON."
    if kind in ("model_attributes_type", "dict_type"):
        return "Expected a JSON object."
    return error["msg"]


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with one message per field: {"errors": {"latitude": "Must be at most 90."}}."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        # loc looks like ("body", "latitude") or ("query", "capacityKwh").
        parts = [str(part) for part in error["loc"][1:]]
        field = "body" if error["type"] == "json_invalid" else ".".join(parts) or "body"
        errors.setdefault(field, _message(error))  # keep the first message per field
    return JSONResponse(status_code=422, content={"detail": "Some fields are invalid.", "errors": errors})


async def pvgis_error_handler(request: Request, exc: PvgisError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
