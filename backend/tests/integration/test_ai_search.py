import asyncio
import json
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from client_auth import authenticate_client
from sqlalchemy import delete, func, select
from test_read_api import data  # noqa: F401

from app.ai.client import LLMUnavailable
from app.ai.router import get_llm
from app.ai.service import reserve_call
from app.core.config import Settings
from app.main import create_app
from app.models import AIUsage, Booking


class Model:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def extract(self, text, now, timezone):
        self.calls.append((text, now, timezone))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def preference(day, **changes):
    return json.dumps(
        {
            "date": day.isoformat(),
            "time_from": "10:00",
            "time_to": "12:00",
            "needs_clarification": False,
            "reason": None,
            **changes,
        }
    )


@pytest_asyncio.fixture
async def api(database, data):  # noqa: F811
    app = create_app(Settings(_env_file=None, database_url=database, environment="test"))
    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as session, session.begin():
            await session.execute(delete(AIUsage))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await authenticate_client(client)
            yield app, client


@pytest.mark.asyncio
async def test_search_uses_real_availability_and_never_books(api, data, caplog):  # noqa: F811
    app, client = api
    start, ids = data
    model = Model(preference(start.date()))
    app.dependency_overrides[get_llm] = lambda: model
    async with app.state.session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(Booking))
    response = await client.post(
        "/api/v1/specialists/fixture/search", json={"text": "завтра с 10 до 12"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    # Closed, booked, past and another specialist's slots cannot enter the result.
    assert [slot["id"] for slot in body["items"]] == [str(ids[0]), str(ids[3])]
    assert body["from"].endswith("+06:00") and body["timezone"] == "Asia/Omsk"
    assert model.calls[0][2] == "Asia/Omsk" and model.calls[0][1].utcoffset() == timedelta(hours=6)
    assert response.headers["cache-control"] == "no-store"
    async with app.state.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Booking)) == before
        assert await session.scalar(select(AIUsage.calls)) == 1
    assert "завтра с 10 до 12" not in caplog.text
    # A later booking still uses the ordinary transactional endpoint and conflict handling.
    payload = {"slot_id": str(ids[0]), "client_name": "Test", "client_email": "test@example.com"}
    booked = await client.post("/api/v1/bookings", json=payload)
    assert booked.status_code == 201
    assert (await client.post("/api/v1/bookings", json=payload)).status_code == 409
    again = await client.post("/api/v1/specialists/fixture/search", json={"text": "завтра"})
    assert [slot["id"] for slot in again.json()["items"]] == [str(ids[3])]
    # Restore the fixture's availability for independent tests.
    assert (
        await client.post(
            f"/api/v1/bookings/{booked.json()['id']}/cancel",
            headers={"Authorization": f"Bearer {booked.json()['manage_token']}"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_empty_clarification_disabled_and_invalid_provider(api, data):  # noqa: F811
    app, client = api
    path = "/api/v1/specialists/fixture/search"
    assert (await client.post(path, json={"text": "завтра"})).json()["status"] == "unavailable"
    cases = [
        (preference(data[0].date() + timedelta(days=1)), "empty"),
        (preference(data[0].date(), needs_clarification=True, reason="time"), "clarification"),
        (preference(data[0].date(), date="2000-01-01"), "clarification"),
        (preference(data[0].date(), slot_id="made-up"), "unavailable"),
        ('{"tool": "create_booking"}', "unavailable"),
        (LLMUnavailable("PRIVATE upstream detail"), "unavailable"),
    ]
    for output, status in cases:
        model = Model(output)
        app.dependency_overrides[get_llm] = lambda model=model: model
        result = await client.post(path, json={"text": "PRIVATE user text"})
        assert result.status_code == 200
        assert result.json()["status"] == status and result.json()["items"] == []
        assert "PRIVATE" not in result.text and "made-up" not in result.text


@pytest.mark.asyncio
async def test_invalid_input_and_missing_specialist_do_not_spend_budget(api, data):  # noqa: F811
    app, client = api
    model = Model(preference(data[0].date()))
    app.dependency_overrides[get_llm] = lambda: model
    for body in [{"text": " "}, {"text": "a" * 501}, {"text": "ok", "specialist_id": "other"}]:
        assert (
            await client.post("/api/v1/specialists/fixture/search", json=body)
        ).status_code == 422
    assert (
        await client.post("/api/v1/specialists/missing/search", json={"text": "завтра"})
    ).status_code == 404
    assert model.calls == []
    async with app.state.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsage)) == 0


@pytest.mark.asyncio
async def test_durable_budget_is_atomic_and_failures_consume_it(api):
    app, client = api

    async def attempt():
        async with app.state.session_factory() as session:
            return await reserve_call(session, 3)

    results = await asyncio.gather(*[attempt() for _ in range(20)])
    assert sum(results) == 3
    async with app.state.session_factory() as session:
        assert await session.scalar(select(AIUsage.calls)) == 3
    app.state.settings.ai_daily_request_limit = 4
    model = Model(LLMUnavailable())
    app.dependency_overrides[get_llm] = lambda: model
    for _ in range(2):
        assert (
            await client.post("/api/v1/specialists/fixture/search", json={"text": "завтра"})
        ).json()["status"] == "unavailable"
    assert len(model.calls) == 1
    # A fresh API process sees the committed count too.
    fresh = create_app(Settings(_env_file=None, database_url=app.state.settings.database_url))
    async with fresh.router.lifespan_context(fresh), fresh.state.session_factory() as session:
        assert not await reserve_call(session, 4)
