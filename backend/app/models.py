"""Database tables."""

import time

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> int:
    return int(time.time())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2id, never the password
    created_at: Mapped[int] = mapped_column(default=_now)


class AuthSession(Base):
    """A logged-in browser. The cookie holds a random token; we only store its hash."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 hex
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(index=True)  # unix seconds

    user: Mapped[User] = relationship()


class Site(Base):
    __tablename__ = "sites"
    # AUTOINCREMENT: ids of deleted sites are never handed out again.
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float]
    longitude: Mapped[float]
    roof_area_m2: Mapped[float | None]
    peak_kwp: Mapped[float]
    created_at: Mapped[int] = mapped_column(default=_now)
    updated_at: Mapped[int] = mapped_column(default=_now, onupdate=_now)
