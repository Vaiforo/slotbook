import json
import subprocess
import sys
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import create_app


@pytest.mark.asyncio
async def test_safe_errors_request_ids_and_logging(caplog):
    app = create_app(Settings(_env_file=None))

    @app.get("/broken")
    async def broken():
        raise RuntimeError("SECRET DATABASE VALUE")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        caplog.set_level("INFO", logger="app.core.errors")
        responses = [
            await client.get("/broken?token=SECRET QUERY"),
            await client.get("/unknown"),
            await client.post("/health/live"),
        ]
    assert [r.status_code for r in responses] == [500, 404, 405]
    assert responses[2].headers["allow"] == "GET"
    ids = []
    for response in responses:
        error = response.json()["error"]
        assert set(error) == {"code", "message", "request_id"}
        assert error["request_id"] == response.headers["x-request-id"]
        UUID(error["request_id"])
        ids.append(error["request_id"])
        assert "SECRET" not in response.text
    assert len(set(ids)) == 3
    records = [
        json.loads(JsonFormatter().format(r)) for r in caplog.records if r.name == "app.core.errors"
    ]
    assert len(records) == 3
    assert [r["request_id"] for r in records] == ids
    assert "SECRET" not in json.dumps(records)
    assert records[0]["route"] == "/broken"


def test_openapi_export_without_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SLOTBOOK_DATABASE_URL", "not-even-a-database-url")
    output = tmp_path / "openapi.json"
    subprocess.run(
        [sys.executable, "-m", "scripts.export_openapi", "--output", str(output)], check=True
    )
    schema = json.loads(output.read_text())
    assert set(schema["paths"]) == {
        "/health/live",
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
    }
    assert "manage_token_hash" not in output.read_text()
    assert "BookingCreated" in schema["components"]["schemas"]
    assert schema["paths"]["/api/v1/specialists/{slug}/slots"]["get"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
