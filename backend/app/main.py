from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models  # noqa: F401  (importing registers the tables)
from .config import Settings
from .db import create_tables, make_engine

settings = Settings.from_env()
engine = make_engine(settings.data_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables(engine, settings.data_dir)
    yield
    engine.dispose()


app = FastAPI(title="Solar sites", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}