import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.errors import ErrorResponse, install_error_handling
from app.core.logging import configure_logging
from app.modules.specialists.router import router

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
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield
        finally:
            await engine.dispose()
        logger.info("SlotBook API stopped")

    app = FastAPI(
        title=settings.app_name,
        version="0.0.0",
        lifespan=lifespan,
        responses={code: {"model": ErrorResponse} for code in (404, 405, 422, 500)},
    )
    install_error_handling(app)
    app.include_router(router)

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    async def live(response: Response) -> LiveResponse:
        """Liveness only; does not check database readiness."""
        response.headers["Cache-Control"] = "no-store"
        return LiveResponse(service=settings.app_name)

    return app


app = create_app()
