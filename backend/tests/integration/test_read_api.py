from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, insert, select, text

from app.core.config import Settings
from app.main import create_app
from app.models import Booking, Slot, Specialist, User
from scripts.seed_demo import DEMO_SPECIALIST, seed_demo


@pytest.fixture(scope="module")
def data(database):
    seed_demo(database)
    engine = create_engine(database)
    with engine.begin() as conn:
        now = conn.scalar(text("SELECT CURRENT_TIMESTAMP"))
        start = datetime.combine(
            now.astimezone(ZoneInfo("Asia/Omsk")).date() + timedelta(days=1),
            time(10),
            ZoneInfo("Asia/Omsk"),
        )
        ids = list(
            conn.scalars(
                select(Slot.id)
                .where(Slot.specialist_id == DEMO_SPECIALIST)
                .order_by(Slot.starts_at)
            )
        )
        conn.execute(Slot.__table__.update().where(Slot.id == ids[1]).values(state="closed"))
        for slot_id, status, token in [(ids[2], "confirmed", "a"), (ids[3], "cancelled", "b")]:
            conn.execute(
                insert(Booking).values(
                    slot_id=slot_id,
                    client_name="PRIVATE NAME",
                    client_email="private@example.invalid",
                    status=status,
                    manage_token_hash=token * 64,
                    cancelled_at=now if status == "cancelled" else None,
                )
            )
        for delta in [-2, 31]:
            begins = start + timedelta(days=delta)
            conn.execute(
                insert(Slot).values(
                    specialist_id=DEMO_SPECIALIST,
                    starts_at=begins,
                    ends_at=begins + timedelta(minutes=30),
                )
            )
        owner = conn.scalar(
            insert(User)
            .values(normalized_email="other@example.invalid", password_hash="PRIVATE HASH")
            .returning(User.id)
        )
        other = conn.scalar(
            insert(Specialist)
            .values(user_id=owner, slug="other", display_name="Other")
            .returning(Specialist.id)
        )
        conn.execute(
            insert(Slot).values(
                specialist_id=other, starts_at=start, ends_at=start + timedelta(minutes=30)
            )
        )
    engine.dispose()
    return start, ids


@pytest_asyncio.fixture
async def client(database, data):
    app = create_app(Settings(_env_file=None, database_url=database, environment="test"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


def filters(start, **changes):
    return {"from": start.isoformat(), "to": (start + timedelta(days=1)).isoformat(), **changes}


@pytest.mark.asyncio
async def test_public_profile_and_available_slots(client, data):
    start, ids = data
    profile = await client.get("/api/v1/specialists/demo")
    assert profile.status_code == 200
    assert profile.json() == {
        "id": str(DEMO_SPECIALIST),
        "slug": "demo",
        "display_name": "Демо-специалист",
        "timezone": "Asia/Omsk",
    }
    response = await client.get("/api/v1/specialists/demo/slots", params=filters(start))
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(ids[0]), str(ids[3])]
    assert body["limit"] == 100 and body["offset"] == 0
    for item in body["items"]:
        assert set(item) == {"id", "starts_at", "ends_at"}
        assert datetime.fromisoformat(item["starts_at"]).tzinfo is not None
    assert "private" not in response.text.lower()
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_boundaries_pagination_and_timezone(client, data):
    start, ids = data
    for from_ in [start, start.astimezone(UTC)]:
        response = await client.get(
            "/api/v1/specialists/demo/slots",
            params={"from": from_.isoformat(), "to": (start + timedelta(days=31)).isoformat()},
        )
        assert response.status_code == 200
        assert [x["id"] for x in response.json()["items"]] == [str(ids[0]), str(ids[3])]
    first = await client.get("/api/v1/specialists/demo/slots", params=filters(start, limit=1))
    second = await client.get(
        "/api/v1/specialists/demo/slots", params=filters(start, limit=1, offset=1)
    )
    assert first.json()["items"][0]["id"] == str(ids[0])
    assert second.json()["items"][0]["id"] == str(ids[3])
    exclusive = await client.get(
        "/api/v1/specialists/demo/slots",
        params=filters(start - timedelta(hours=1), to=start.isoformat()),
    )
    assert exclusive.json()["items"] == []
    past = await client.get(
        "/api/v1/specialists/demo/slots", params=filters(start - timedelta(days=2))
    )
    assert past.json()["items"] == []
    empty = await client.get("/api/v1/specialists/demo/slots", params=filters(start, offset=99))
    assert empty.json()["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"from": "2030-01-01T10:00:00"},
        {"to": "not-a-date"},
        {"limit": 101},
        {"limit": 0},
        {"offset": -1},
        {"offset": 10001},
        {"secret": "PRIVATE TOKEN"},
        {"from": None},
    ],
)
async def test_invalid_query_has_safe_error(client, data, changes):
    params = filters(data[0], **changes)
    if params.get("from") is None:
        del params["from"]
    response = await client.get("/api/v1/specialists/demo/slots", params=params)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["request_id"] == response.headers["x-request-id"]
    assert "PRIVATE TOKEN" not in response.text


@pytest.mark.asyncio
async def test_invalid_ranges_and_not_found(client, data):
    start = data[0]
    for end in [start, start - timedelta(seconds=1), start + timedelta(days=31, microseconds=1)]:
        response = await client.get(
            "/api/v1/specialists/demo/slots", params=filters(start, to=end.isoformat())
        )
        assert response.status_code == 422
    for path in ["/api/v1/specialists/missing", "/api/v1/specialists/missing/slots"]:
        response = await client.get(path, params=filters(start))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
