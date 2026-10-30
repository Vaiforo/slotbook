import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings
from app.core.errors import DomainError, ErrorResponse, install_error_handling
from app.core.logging import configure_logging
from app.modules.bookings.router import router as bookings_router
from app.modules.owner.router import router as owner_router
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
    app.state.settings = settings
    app.include_router(owner_router)
    app.add_middleware(BodyLimitMiddleware)
    install_error_handling(app)
    app.include_router(router)
    app.include_router(bookings_router)

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    async def live(response: Response) -> LiveResponse:
        """Liveness only; does not check database readiness."""
        response.headers["Cache-Control"] = "no-store"
        return LiveResponse(service=settings.app_name)

    @app.get(
        "/health/ready",
        response_model=LiveResponse,
        tags=["health"],
        responses={503: {"model": ErrorResponse}},
    )
    async def ready() -> LiveResponse:
        """Ready only when the database has exactly the packaged migration heads."""
        expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
        try:
            async with asyncio.timeout(3), app.state.session_factory() as session:
                actual = set(
                    (
                        await session.execute(text("SELECT version_num FROM alembic_version"))
                    ).scalars()
                )
                if actual != expected:
                    raise DomainError(503, "not_ready", "Service is not ready")
        except (SQLAlchemyError, TimeoutError) as exc:
            raise DomainError(503, "not_ready", "Service is not ready") from exc
        return LiveResponse(service=settings.app_name)

    return app


app = create_app()
