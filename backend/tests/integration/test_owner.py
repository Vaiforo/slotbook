import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update

from app.core.config import Settings
from app.main import create_app
from app.models import Session, Slot, Specialist, User
from app.modules.owner.security import hasher

PASSWORD = "test-password-for-owner"
ORIGIN = "https://slotbook.example"


@pytest_asyncio.fixture
async def api(database):
    app = create_app(Settings(database_url=database, environment="test", public_origin=ORIGIN))
    async with app.router.lifespan_context(app):
        async with app.state.session_factory.begin() as db:
            users = [
                User(normalized_email=f"{uuid4()}@example.com", password_hash=hasher.hash(PASSWORD))
                for _ in range(2)
            ]
            db.add_all(users)
            await db.flush()
            db.add_all(
                [
                    Specialist(
                        user_id=user.id, slug=str(uuid4()), display_name="Owner", timezone="UTC"
                    )
                    for user in users
                ]
            )
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            yield app, client, users


async def login(client, user):
    response = await client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": user.normalized_email.upper(), "password": PASSWORD},
    )
    assert response.status_code == 204, response.text
    assert "Secure" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": me.json()["csrf_token"]}


def slot_data():
    start = datetime.now(UTC) + timedelta(days=2)
    return {"starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=30)).isoformat()}


@pytest.mark.asyncio
async def test_sessions_csrf_expiry_revocation(api):
    app, client, users = api
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": users[0].normalized_email, "password": PASSWORD}
        )
    ).status_code == 403
    for email in [users[0].normalized_email, "missing@example.com"]:
        assert (
            await client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"email": email, "password": "wrong"},
            )
        ).status_code == 401
    headers = await login(client, users[0])
    old = client.cookies.get("session")
    async with app.state.session_factory() as db:
        session = (await db.scalars(select(Session))).first()
        assert session.token_hash != old
        assert session.csrf_token_hash != headers["X-CSRF-Token"]
    for invalid in [
        {},
        {"Origin": ORIGIN},
        {**headers, "Origin": "https://evil.example"},
        {**headers, "X-CSRF-Token": "bad"},
    ]:
        assert (
            await client.post("/api/v1/slots", headers=invalid, json=slot_data())
        ).status_code == 403
    headers = await login(client, users[0])
    assert client.cookies.get("session") != old
    assert (
        await client.get("/api/v1/auth/me", headers={"Cookie": f"session={old}"})
    ).status_code == 401
    token = client.cookies.get("session")
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert (
        await client.get("/api/v1/auth/me", headers={"Cookie": f"session={token}"})
    ).status_code == 401
    await login(client, users[0])
    async with app.state.session_factory.begin() as db:
        await db.execute(
            update(Session)
            .where(Session.user_id == users[0].id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_slots_ownership_overlap_and_booking_list(api):
    _, client, users = api
    headers = await login(client, users[0])
    data = slot_data()
    response = await client.post("/api/v1/slots", headers=headers, json=data)
    assert response.status_code == 201, response.text
    slot = response.json()
    assert (await client.post("/api/v1/slots", headers=headers, json=data)).status_code == 409
    assert (
        await client.post(
            "/api/v1/slots", headers=headers, json={**data, "specialist_id": str(uuid4())}
        )
    ).status_code == 422
    booked = await client.post(
        "/api/v1/bookings",
        json={
            "slot_id": slot["id"],
            "client_name": "Private",
            "client_email": "private@example.com",
        },
    )
    assert booked.status_code == 201
    assert (
        await client.patch(f"/api/v1/slots/{slot['id']}", headers=headers, json={"state": "closed"})
    ).status_code == 409
    params = {"from": data["starts_at"], "to": data["ends_at"], "status": "confirmed"}
    listing = await client.get("/api/v1/me/bookings", params=params)
    assert len(listing.json()["items"]) == 1
    assert "manage_token" not in listing.text
    assert listing.headers["cache-control"] == "no-store"
    other = await login(client, users[1])
    assert (await client.get("/api/v1/me/bookings", params=params)).json()["items"] == []
    assert (
        await client.patch(f"/api/v1/slots/{slot['id']}", headers=other, json={"state": "closed"})
    ).status_code == 404
    assert (await client.post("/api/v1/slots", headers=other, json=data)).status_code == 201
    headers = await login(client, users[0])
    booking = booked.json()
    assert (
        await client.post(
            f"/api/v1/bookings/{booking['id']}/cancel",
            headers={"Authorization": f"Bearer {booking['manage_token']}"},
        )
    ).status_code == 200
    for state in ["closed", "open"]:
        changed = await client.patch(
            f"/api/v1/slots/{slot['id']}", headers=headers, json={"state": state}
        )
        assert changed.status_code == 200
        assert changed.json()["state"] == state


@pytest.mark.asyncio
async def test_close_and_book_are_serialized(api):
    app, client, users = api
    headers = await login(client, users[0])
    slot = (await client.post("/api/v1/slots", headers=headers, json=slot_data())).json()
    # Hold the shared row lock until both independent requests have been scheduled.
    async with app.state.session_factory.begin() as db:
        await db.scalar(select(Slot).where(Slot.id == slot["id"]).with_for_update())
        close = asyncio.create_task(
            client.patch(f"/api/v1/slots/{slot['id']}", headers=headers, json={"state": "closed"})
        )
        book = asyncio.create_task(
            client.post(
                "/api/v1/bookings",
                json={
                    "slot_id": slot["id"],
                    "client_name": "Client",
                    "client_email": "client@example.com",
                },
            )
        )
        blocker_pid = await db.scalar(select(func.pg_backend_pid()))
        try:
            async with asyncio.timeout(10):
                async with app.state.session_factory() as observer:
                    while True:
                        await observer.execute(select(func.pg_stat_clear_snapshot()))
                        waiting = await observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                                "AND pid <> :pid"
                            ),
                            {"pid": blocker_pid},
                        )
                        if waiting == 2:
                            break
                        await asyncio.sleep(0.02)
        except BaseException:
            close.cancel()
            book.cancel()
            await asyncio.gather(close, book, return_exceptions=True)
            raise
    closed, booked = await asyncio.wait_for(asyncio.gather(close, book), timeout=10)
    assert (closed.status_code, booked.status_code) in {(200, 409), (409, 201)}
    async with app.state.session_factory() as db:
        state = await db.scalar(select(Slot.state).where(Slot.id == slot["id"]))
        assert state == ("closed" if closed.status_code == 200 else "open")


def test_plain_http_only_for_development_loopback():
    for origin in ["http://example.com", "http://127.0.0.1:5173"]:
        with pytest.raises(ValueError):
            Settings(environment="production", public_origin=origin)
    Settings(environment="production", public_origin=ORIGIN)
    Settings(environment="development", public_origin="http://127.0.0.1:5173")


@pytest.mark.asyncio
async def test_owner_mutations_require_auth_and_validate_dates(api):
    _, client, users = api
    data = slot_data()
    assert (await client.post("/api/v1/slots", json=data)).status_code == 401
    headers = await login(client, users[0])
    for invalid in [
        {**data, "ends_at": data["starts_at"]},
        {**data, "starts_at": "2030-01-01T10:00:00"},
    ]:
        assert (
            await client.post("/api/v1/slots", headers=headers, json=invalid)
        ).status_code == 422
    past = datetime.now(UTC) - timedelta(hours=1)
    assert (
        await client.post(
            "/api/v1/slots",
            headers=headers,
            json={
                "starts_at": past.isoformat(),
                "ends_at": (past + timedelta(minutes=30)).isoformat(),
            },
        )
    ).status_code == 409
    assert (
        await client.get(
            "/api/v1/me/bookings", params={"from": data["starts_at"], "to": data["starts_at"]}
        )
    ).status_code == 422


def test_seed_password_is_opt_in_and_repeatable(database):
    from sqlalchemy import create_engine

    from app.modules.owner.security import verify_password
    from scripts.seed_demo import DEMO_USER, seed_demo

    seed_demo(database, password=PASSWORD)
    seed_demo(database)
    engine = create_engine(database)
    try:
        with engine.connect() as conn:
            encoded = conn.scalar(select(User.password_hash).where(User.id == DEMO_USER))
            assert encoded.startswith("$argon2id$")
            assert verify_password(PASSWORD, encoded)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_schedule_lists_closed_and_occupied_slots_only_for_owner(api):
    _, client, users = api
    headers = await login(client, users[0])
    identity = (await client.get("/api/v1/auth/me")).json()
    assert identity["specialist"]["timezone"] == "UTC"
    first = slot_data()
    slot = (await client.post("/api/v1/slots", headers=headers, json=first)).json()
    filters = {"from": first["starts_at"], "to": first["ends_at"]}
    listing = await client.get("/api/v1/me/slots", params=filters)
    assert listing.json()["items"][0]["has_booking"] is False
    await client.patch(f"/api/v1/slots/{slot['id']}", headers=headers, json={"state": "closed"})
    assert (await client.get("/api/v1/me/slots", params=filters)).json()["items"][0][
        "state"
    ] == "closed"
    await client.patch(f"/api/v1/slots/{slot['id']}", headers=headers, json={"state": "open"})
    await client.post(
        "/api/v1/bookings",
        json={
            "slot_id": slot["id"],
            "client_name": "Private",
            "client_email": "private@example.com",
        },
    )
    listing = await client.get("/api/v1/me/slots", params=filters)
    assert listing.json()["items"][0]["has_booking"] is True
    assert "client_email" not in listing.text
    assert (await client.get("/api/v1/me/slots", params={**filters, "offset": 1})).json()[
        "items"
    ] == []
    assert (await client.get("/api/v1/me/slots", params={**filters, "limit": 0})).status_code == 422
    await login(client, users[1])
    assert (await client.get("/api/v1/auth/me")).json()["specialist"]["id"] != identity[
        "specialist"
    ]["id"]
    assert (await client.get("/api/v1/me/slots", params=filters)).json()["items"] == []
    client.cookies.clear()
    assert (await client.get("/api/v1/me/slots", params=filters)).status_code == 401
