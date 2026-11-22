from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import sessionmaker

from . import models  # noqa: F401
from .config import Settings
from .db import create_tables, make_engine
from .errors import validation_error_handler
from .rate_limit import LoginThrottle
from .routers import auth


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = make_engine(settings.data_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        create_tables(engine, settings.data_dir)
        yield
        engine.dispose()

    app = FastAPI(title="Solar sites", lifespan=lifespan, docs_url="/api/docs",
                  redoc_url=None, openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.login_throttle = LoginThrottle(settings.login_max_failures,
                                             settings.login_window_seconds)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(auth.router)
    return app


app = create_app()