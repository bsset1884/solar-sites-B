"""Database setup: SQLAlchemy 2.0 with a SQLite file."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def make_engine(data_dir: Path) -> Engine:
    # FastAPI runs our (sync) endpoints in a thread pool, so a connection may be
    # used by another thread than the one that opened it. Every request gets its
    # own Session, so this is safe.
    engine = create_engine(
        f"sqlite:///{data_dir / 'solar.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
        cursor.execute("PRAGMA journal_mode = WAL")  # readers do not block the writer
        cursor.close()

    return engine


def create_tables(engine: Engine, data_dir: Path) -> None:
    """Create the data folder and any missing tables (no migrations needed yet)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def get_db(request: Request) -> Iterator[Session]:
    """One database session per request, closed when the request is done."""
    with request.app.state.session_factory() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]
