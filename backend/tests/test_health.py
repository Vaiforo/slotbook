import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import create_app


@pytest.mark.asyncio
async def test_live_contract_and_no_placeholder_routes() -> None:
    app = create_app(Settings(_env_file=None))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "SlotBook"}
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get("/api/v1/not-implemented")).status_code == 404
        assert set((await client.get("/openapi.json")).json()["paths"]) == {
            "/health/live",
            "/health/ready",
            "/api/v1/specialists/{slug}",
            "/api/v1/specialists/{slug}/slots",
            "/api/v1/bookings",
            "/api/v1/bookings/{booking_id}",
            "/api/v1/bookings/{booking_id}/cancel",
            "/api/v1/auth/login",
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/slots",
            "/api/v1/slots/{slot_id}",
            "/api/v1/me/bookings",
            "/api/v1/me/slots",
        }


@pytest.mark.asyncio
async def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLOTBOOK_APP_NAME", "SlotBook test")
    app = create_app(Settings(_env_file=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health/live")).json()["service"] == "SlotBook test"
    monkeypatch.setenv("SLOTBOOK_LOG_LEVEL", "invalid")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_log_message_is_valid_json() -> None:
    record = logging.LogRecord("slotbook", logging.INFO, __file__, 1, 'Hello "API"', (), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == 'Hello "API"'
    assert payload["level"] == "INFO"
    assert payload["timestamp"].endswith("+00:00")
