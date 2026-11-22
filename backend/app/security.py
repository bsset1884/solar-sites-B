"""Passwords, sessions and CSRF protection."""

import hashlib
import hmac
import secrets
import time
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import DbSession
from .models import AuthSession, User

SESSION_COOKIE = "session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}  # methods that never change data

# Argon2id with the minimum settings OWASP recommends (19 MiB memory, 2 passes).
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
# Checked when an email does not exist, so that costs as much time as a wrong
# password and the response time does not reveal which emails have accounts.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)  # includes a random salt


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        _hasher.verify(stored_hash or _DUMMY_HASH, password)
    except VerifyMismatchError:
        return False
    return stored_hash is not None


def _hash_token(token: str) -> str:
    # The token is 256 random bits, so a fast hash is safe (there is nothing to
    # guess). If the database leaks, the stored hashes are no working cookies.
    return hashlib.sha256(token.encode()).hexdigest()


def find_session(request: Request, db: Session) -> AuthSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.get(AuthSession, _hash_token(token))
    if session is None or session.expires_at <= time.time():
        return None
    return session


def start_session(request: Request, response: Response, db: Session, user: User) -> str:
    """Log the browser in: store a new session, set the cookie, return the CSRF token."""
    settings = request.app.state.settings
    now = int(time.time())

    old = find_session(request, db)
    if old is not None:  # a new login replaces this browser's old session
        db.delete(old)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))  # tidy up

    token = secrets.token_urlsafe(32)  # 256 bits, unguessable
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            csrf_token=csrf_token,
            expires_at=now + settings.session_ttl_seconds,
        )
    )
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,  # JavaScript cannot read it, so an XSS bug cannot steal it
        samesite="strict",  # the browser does not send it with requests from other sites
        secure=settings.cookie_secure or request.url.scheme == "https",
        path="/",
    )
    return csrf_token


def end_session(request: Request, response: Response, db: Session) -> None:
    session = find_session(request, db)
    if session is not None:
        check_csrf(request, session)
        db.delete(session)  # deleted on the server, so the old cookie is worthless
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")


def check_csrf(request: Request, session: AuthSession) -> None:
    """Requests that change data must echo the session's CSRF token in a header.

    Another website can make the browser send our cookie (in old browsers or
    from a sibling subdomain), but it cannot read or send this token.
    """
    sent = request.headers.get(CSRF_HEADER, "")
    # compare_digest takes the same time wherever the strings differ.
    if not hmac.compare_digest(sent.encode(), session.csrf_token.encode()):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token.")


def get_current_session(request: Request, db: DbSession) -> AuthSession:
    session = find_session(request, db)
    if session is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    if request.method not in SAFE_METHODS:
        check_csrf(request, session)
    return session


CurrentSession = Annotated[AuthSession, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]
