import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from app.core.config import Settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        logger.info("SlotBook API started (%s)", settings.environment)
        yield
        logger.info("SlotBook API stopped")

    app = FastAPI(title=settings.app_name, version="0.0.0", lifespan=lifespan)

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    async def live(response: Response) -> LiveResponse:
        """Liveness only; database readiness is added with the database stage."""
        response.headers["Cache-Control"] = "no-store"
        return LiveResponse(service=settings.app_name)

    return app


app = create_app()
