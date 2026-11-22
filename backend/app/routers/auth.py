"""Accounts and sessions: /api/register, /api/login, /api/logout, /api/me."""

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import DbSession
from ..models import User
from ..schemas import AuthOut, ErrorOut, LoginIn, RegisterIn, ValidationErrorOut
from ..security import CurrentSession, end_session, hash_password, start_session, verify_password

router = APIRouter(prefix="/api", tags=["auth"], responses={422: {"model": ValidationErrorOut}})

EMAIL_TAKEN = "An account with this email already exists."


@router.post("/register", status_code=201, response_model=AuthOut, responses={409: {"model": ErrorOut}})
def register(body: RegisterIn, request: Request, response: Response, db: DbSession) -> AuthOut:
    """201 Created: a new account now exists, and this browser is logged in."""
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN)

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()  # INSERT now: the UNIQUE constraint also catches two sign-ups at once
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN) from None

    csrf_token = start_session(request, response, db, user)
    return AuthOut(email=user.email, csrf_token=csrf_token)


@router.post(
    "/login",
    response_model=AuthOut,
    responses={401: {"model": ErrorOut}, 429: {"model": ErrorOut}},
)
def login(body: LoginIn, request: Request, response: Response, db: DbSession) -> AuthOut:
    throttle = request.app.state.login_throttle
    wait = throttle.retry_after(body.email)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please wait and try again.",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(select(User).where(User.email == body.email))
    # Always check a password, also for unknown emails, so both cases take as long.
    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or not password_ok:
        throttle.record_failure(body.email)
        # One message for both cases: do not reveal which emails have an account.
        raise HTTPException(status_code=401, detail="Wrong email or password.")

    throttle.reset(body.email)
    csrf_token = start_session(request, response, db, user)
    return AuthOut(email=user.email, csrf_token=csrf_token)


@router.post("/logout", status_code=204, responses={403: {"model": ErrorOut}})
def logout(request: Request, response: Response, db: DbSession) -> None:
    """204 No Content. Also 204 without a session: the result (logged out) is the same."""
    end_session(request, response, db)


@router.get("/me", response_model=AuthOut, responses={401: {"model": ErrorOut}})
def me(session: CurrentSession) -> AuthOut:
    """Who is logged in. The page calls this when it loads, which also gives it
    the CSRF token again (the page keeps that token only in memory)."""
    return AuthOut(email=session.user.email, csrf_token=session.csrf_token)
