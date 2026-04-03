"""FastAPI application for monitoring, import, and export."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Property Data Collector",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
