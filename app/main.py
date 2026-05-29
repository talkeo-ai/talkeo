from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL, env=settings.ENV)
    yield


app = FastAPI(
    title="Talkeo",
    version="0.0.1",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api")
