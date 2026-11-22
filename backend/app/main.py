"""The FastAPI application: the API under /api, the React app on all other paths.

Start it with:  uvicorn app.main:app
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from . import models  # noqa: F401  (importing registers the tables)
from .config import Settings
from .db import create_tables, make_engine
from .errors import pvgis_error_handler, validation_error_handler
from .pvgis import PvgisClient, PvgisError
from .rate_limit import LoginThrottle
from .routers import auth, sites

# The browser may only load scripts, styles, fonts and data from our own origin,
# and no other site may show our pages in a frame (clickjacking).
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def add_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built React app next to the API.

    /assets/... are the bundled files. Every other GET that is not an API route
    gets index.html, so reloading /sites/3 works: React Router then shows the page.
    """
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")  # unknown API route: no HTML
        if "." in path.rsplit("/", 1)[-1]:  # looks like a file, e.g. favicon.svg
            file = static_dir / path
            # Only files directly in static_dir, so "../" tricks cannot reach other files.
            if "/" not in path and file.is_file():
                return FileResponse(file)
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(static_dir / "index.html")


def create_app(settings: Settings | None = None, pvgis: PvgisClient | None = None) -> FastAPI:
    """Build the app. Tests call this with their own settings and a fake PVGIS."""
    settings = settings or Settings.from_env()
    engine = make_engine(settings.data_dir)
    pvgis_client = pvgis or PvgisClient(settings.pvgis_base_url, settings.pvgis_timeout_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        create_tables(engine, settings.data_dir)  # on startup
        yield
        pvgis_client.close()  # on shutdown
        engine.dispose()

    app = FastAPI(
        title="Solar sites",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.pvgis = pvgis_client
    app.state.login_throttle = LoginThrottle(
        settings.login_max_failures, settings.login_window_seconds
    )

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PvgisError, pvgis_error_handler)

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"  # personal data: never cache
        if not path.startswith("/api/docs"):  # the Swagger UI page loads scripts from a CDN
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response

    app.include_router(auth.router)
    app.include_router(sites.router)

    if (settings.static_dir / "index.html").is_file():
        add_frontend(app, settings.static_dir)  # last, so the API routes come first

    return app


app = create_app()
