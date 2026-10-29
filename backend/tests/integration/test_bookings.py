import asyncio
import hashlib
import secrets
import socket
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import uvicorn
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.core.db import get_session
from app.main import create_app
from app.models import Booking, Slot, Specialist, User
from app.modules.bookings import repository, service


@pytest_asyncio.fixture
async def api(database):
    app = create_app(Settings(_env_file=None, database_url=database, environment="test"))
    async with app.router.lifespan_context(app):
        async with app.state.session_factory() as session, session.begin():
            owner = User(normalized_email=f"{uuid4()}@example.com", password_hash="!disabled")
            session.add(owner)
            await session.flush()
            specialist = Specialist(
                user_id=owner.id, slug=str(uuid4()), display_name="Test", timezone="Asia/Omsk"
            )
            session.add(specialist)
            await session.flush()
            specialist_id, slug = specialist.id, specialist.slug

        async def new_slot(*, state="open", delay=3600):
            async with app.state.session_factory() as session, session.begin():
                now = await repository.database_time(session)
                starts = now + timedelta(seconds=delay)
                slot = Slot(
                    specialist_id=specialist_id,
                    starts_at=starts,
                    ends_at=starts + timedelta(minutes=30),
                    state=state,
                )
                session.add(slot)
                await session.flush()
                return slot.id

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client, new_slot, slug


def payload(slot, **changes):
    return {
        "slot_id": str(slot),
        "client_name": "  Анна Тестовая  ",
        "client_email": "client@example.com",
        **changes,
    }


def headers(created):
    return {"Authorization": f"Bearer {created['manage_token']}"}


async def snapshot(app, slot_id):
    async with app.state.session_factory() as session:
        return list(
            (await session.scalars(select(Booking).where(Booking.slot_id == slot_id))).all()
        )


@pytest.mark.asyncio
async def test_create_get_cancel_rebook_and_old_cancel(api, caplog):
    app, client, new_slot, slug = api
    slot_id = await new_slot()
    response = await client.post("/api/v1/bookings", json=payload(slot_id))
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["status"] == "confirmed" and first["client_name"] == "Анна Тестовая"
    assert len(first["manage_token"]) == 43
    for header, value in [("cache-control", "no-store"), ("referrer-policy", "no-referrer")]:
        assert response.headers[header] == value
    rows = await snapshot(app, slot_id)
    assert len(rows) == 1
    assert rows[0].manage_token_hash == hashlib.sha256(first["manage_token"].encode()).hexdigest()
    assert rows[0].manage_token_hash != first["manage_token"]
    path = f"/api/v1/bookings/{first['id']}"
    details = await client.get(path, headers=headers(first))
    assert details.status_code == 200
    assert "manage_token" not in details.json() and "manage_token_hash" not in details.text
    assert details.json()["status"] == "confirmed"  # GET never cancels.
    query = {"from": first["starts_at"], "to": first["ends_at"]}
    available = f"/api/v1/specialists/{slug}/slots"
    assert (await client.get(available, params=query)).json()["items"] == []
    cancelled = await client.post(path + "/cancel", headers=headers(first))
    assert cancelled.status_code == 200 and cancelled.json()["cancelled_at"] is not None
    assert [x["id"] for x in (await client.get(available, params=query)).json()["items"]] == [
        str(slot_id)
    ]
    second = await client.post("/api/v1/bookings", json=payload(slot_id))
    assert second.status_code == 201
    repeat = await client.post(path + "/cancel", headers=headers(first))
    assert repeat.json() == cancelled.json()
    rows = await snapshot(app, slot_id)
    assert {row.id: row.status for row in rows} == {
        UUID(first["id"]): "cancelled",
        UUID(second.json()["id"]): "confirmed",
    }
    assert (await client.get(available, params=query)).json()["items"] == []
    assert any(r.name == "app.core.errors" for r in caplog.records)
    log_text = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app."))
    for secret in [
        first["manage_token"],
        rows[0].manage_token_hash,
        "client@example.com",
        "Анна Тестовая",
    ]:
        assert secret not in log_text


@pytest.mark.asyncio
@pytest.mark.parametrize("state,delay", [("closed", 3600), ("open", -3600), ("open", 0)])
async def test_unavailable_slot(api, state, delay):
    app, client, new_slot, _ = api
    slot_id = await new_slot(state=state, delay=delay)
    response = await client.post("/api/v1/bookings", json=payload(slot_id))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_unavailable"
    assert await snapshot(app, slot_id) == []


@pytest.mark.asyncio
async def test_missing_slot_and_booking(api):
    _, client, _, _ = api
    assert (await client.post("/api/v1/bookings", json=payload(uuid4()))).status_code == 404
    token = secrets.token_urlsafe(32)
    assert (
        await client.get(
            f"/api/v1/bookings/{uuid4()}", headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_token_authorization_has_no_alternative(api):
    app, client, new_slot, _ = api
    slot_id = await new_slot()
    created = (await client.post("/api/v1/bookings", json=payload(slot_id))).json()
    path = f"/api/v1/bookings/{created['id']}"
    for auth in [
        None,
        "Bearer invalid",
        f"Bearer {secrets.token_urlsafe(32)}",
        f"Basic {created['manage_token']}",
    ]:
        kwargs = {"headers": {"Authorization": auth}} if auth else {}
        for method, url in [("GET", path), ("POST", path + "/cancel")]:
            response = await client.request(method, url, **kwargs)
            assert response.status_code == 404
            assert "client_email" not in response.text
    for method, url in [("GET", path), ("POST", path + "/cancel")]:
        response = await client.request(
            method,
            url,
            params={"token": created["manage_token"]},
            headers={"Cookie": f"session={created['manage_token']}"},
        )
        assert response.status_code == 404
    assert (await snapshot(app, slot_id))[0].status == "confirmed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"client_name": "   "},
        {"client_name": "x" * 201},
        {"client_name": "Name\x00"},
        {"client_email": "invalid"},
        {"slot_id": "bad-id"},
        {"manage_token": "injected"},
        {"status": "cancelled"},
    ],
)
async def test_validation(api, changes):
    app, client, new_slot, _ = api
    slot_id = await new_slot()
    response = await client.post("/api/v1/bookings", json=payload(slot_id, **changes))
    assert response.status_code == 422
    assert await snapshot(app, slot_id) == []


@pytest.mark.asyncio
async def test_streamed_body_limit(api):
    _, client, _, _ = api

    async def chunks():
        for _ in range(20):
            yield b"x" * 1024

    for content in [b"x" * 20000, chunks()]:
        response = await client.post(
            "/api/v1/bookings", content=content, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    bad_json = await client.post(
        "/api/v1/bookings", content=b"{", headers={"Content-Type": "application/json"}
    )
    assert bad_json.status_code == 422


@pytest.mark.asyncio
async def test_only_expected_unique_violation_maps_to_conflict(api, monkeypatch):
    app, client, new_slot, _ = api
    slot_id = await new_slot()
    first = (await client.post("/api/v1/bookings", json=payload(slot_id))).json()

    async def false(*args):
        return False

    monkeypatch.setattr(repository, "has_confirmed_booking", false)
    response = await client.post("/api/v1/bookings", json=payload(slot_id))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_unavailable"
    other = await new_slot(delay=7200)
    monkeypatch.setattr(service, "new_manage_token", lambda: first["manage_token"])
    collision = await client.post("/api/v1/bookings", json=payload(other))
    assert collision.status_code == 500  # Different UNIQUE is not a slot conflict.
    assert first["manage_token"] not in collision.text
    assert await snapshot(app, other) == []


@pytest.mark.asyncio
async def test_create_and_cancel_rollback_after_flush(api, monkeypatch):
    app, client, new_slot, _ = api
    slot_id = await new_slot()
    original = service.details

    def broken(*args):
        raise RuntimeError("PRIVATE CONTACT")

    monkeypatch.setattr(service, "details", broken)
    assert (await client.post("/api/v1/bookings", json=payload(slot_id))).status_code == 500
    assert await snapshot(app, slot_id) == []
    monkeypatch.setattr(service, "details", original)
    created = (await client.post("/api/v1/bookings", json=payload(slot_id))).json()
    monkeypatch.setattr(service, "details", broken)
    failed = await client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers(created))
    assert failed.status_code == 500
    row = (await snapshot(app, slot_id))[0]
    assert row.status == "confirmed" and row.cancelled_at is None
    monkeypatch.setattr(service, "details", original)
    assert (
        await client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers(created))
    ).status_code == 200


@pytest.mark.asyncio
async def test_two_cancellations_refresh_after_lock(api, monkeypatch):
    _, client, new_slot, _ = api
    created = (await client.post("/api/v1/bookings", json=payload(await new_slot()))).json()
    original = repository.get_booking
    barrier = asyncio.Barrier(2)

    async def lookup(*args, **kwargs):
        result = await original(*args, **kwargs)
        if not kwargs.get("lock"):
            await barrier.wait()
        return result

    monkeypatch.setattr(repository, "get_booking", lookup)
    async with asyncio.timeout(10):
        responses = await asyncio.gather(
            *[
                client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers(created))
                for _ in range(2)
            ]
        )
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "cancel"])
async def test_clock_is_checked_after_waiting_for_lock(api, operation):
    app, client, new_slot, _ = api
    slot_id = await new_slot(delay=2)
    created = None
    if operation == "cancel":
        created = (await client.post("/api/v1/bookings", json=payload(slot_id))).json()
    async with app.state.session_factory() as blocker:
        async with blocker.begin():
            await repository.get_slot(blocker, slot_id, lock=True)
            blocker_pid = await blocker.scalar(select(func.pg_backend_pid()))
            if created:
                task = asyncio.create_task(
                    client.post(
                        f"/api/v1/bookings/{created['id']}/cancel", headers=headers(created)
                    )
                )
            else:
                task = asyncio.create_task(client.post("/api/v1/bookings", json=payload(slot_id)))
            try:
                async with asyncio.timeout(8):
                    async with app.state.session_factory() as observer:
                        while not await observer.scalar(
                            text(
                                "SELECT EXISTS (SELECT FROM pg_stat_activity "
                                "WHERE :pid = ANY(pg_blocking_pids(pid)))"
                            ),
                            {"pid": blocker_pid},
                        ):
                            # pg_stat_activity is cached within this observer transaction.
                            await observer.execute(select(func.pg_stat_clear_snapshot()))
                            await asyncio.sleep(0.02)
                        while not await observer.scalar(
                            select(func.clock_timestamp() >= Slot.starts_at).where(
                                Slot.id == slot_id
                            )
                        ):
                            await asyncio.sleep(0.02)
            except BaseException:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
        response = await asyncio.wait_for(task, timeout=5)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == (
        "booking_started" if created else "slot_unavailable"
    )
    rows = await snapshot(app, slot_id)
    assert len(rows) == (1 if created else 0)
    if rows:
        assert rows[0].status == "confirmed"


@pytest.mark.asyncio
async def test_twenty_concurrent_tcp_requests_one_booking(api, database):
    app, _, new_slot, _ = api
    slot_id = await new_slot()
    engine = create_async_engine(database, pool_size=20, max_overflow=0)
    barrier = asyncio.Barrier(20)
    pids = set()

    async def independent_session():
        # Hold twenty distinct connections through the start barrier. Session.begin()
        # must own a fresh transaction, so close the PID query's transaction first.
        async with engine.connect() as connection:
            pids.add(await connection.scalar(select(func.pg_backend_pid())))
            await connection.rollback()
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                await barrier.wait()
                yield session

    app.dependency_overrides[get_session] = independent_session
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", access_log=False, lifespan="off")
    )
    running = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(20):
            while not server.started:
                if running.done():
                    await running
                    raise AssertionError("HTTP server did not start")
                await asyncio.sleep(0.01)

            async def send():
                async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
                    return await client.post(
                        f"http://127.0.0.1:{port}/api/v1/bookings", json=payload(slot_id)
                    )

            responses = await asyncio.gather(*[send() for _ in range(20)])
        assert len(pids) == 20
        assert [r.status_code for r in responses].count(201) == 1
        assert [r.status_code for r in responses].count(409) == 19
        assert all(
            r.json()["error"]["code"] == "slot_unavailable"
            for r in responses
            if r.status_code == 409
        )
        rows = await snapshot(app, slot_id)
        assert len(rows) == 1 and rows[0].status == "confirmed"
    finally:
        server.should_exit = True
        await asyncio.wait_for(running, timeout=5)
        sock.close()
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_does_not_reopen_closed_slot_and_is_idempotent_after_start(api):
    app, client, new_slot, slug = api
    slot_id = await new_slot()
    created = (await client.post("/api/v1/bookings", json=payload(slot_id))).json()
    async with app.state.session_factory() as session, session.begin():
        await session.execute(
            Slot.__table__.update().where(Slot.id == slot_id).values(state="closed")
        )
    path = f"/api/v1/bookings/{created['id']}/cancel"
    first = await client.post(path, headers=headers(created))
    assert first.status_code == 200
    async with app.state.session_factory() as session, session.begin():
        row = await repository.get_slot(session, slot_id)
        assert row.state == "closed"
        # Move only this disposable fixture into the past; there is no time-edit API.
        now = await repository.database_time(session)
        row.starts_at = now - timedelta(hours=1)
        row.ends_at = row.starts_at + timedelta(minutes=30)
    repeat = await client.post(path, headers=headers(created))
    assert repeat.status_code == 200
    # Only the timestamps explicitly changed by this fixture should differ.
    assert datetime.fromisoformat(repeat.json()["starts_at"]) == row.starts_at
    assert datetime.fromisoformat(repeat.json()["ends_at"]) == row.ends_at
    fields = set(first.json()) - {"starts_at", "ends_at"}
    assert {key: repeat.json()[key] for key in fields} == {key: first.json()[key] for key in fields}


@pytest.mark.asyncio
async def test_token_for_another_booking_does_not_authorize(api):
    _, client, new_slot, _ = api
    first = (await client.post("/api/v1/bookings", json=payload(await new_slot()))).json()
    second = (
        await client.post("/api/v1/bookings", json=payload(await new_slot(delay=7200)))
    ).json()
    path = f"/api/v1/bookings/{second['id']}"
    assert (await client.get(path, headers=headers(first))).status_code == 404
    assert (await client.post(path + "/cancel", headers=headers(first))).status_code == 404
    assert (await client.get(path, headers=headers(second))).json()["status"] == "confirmed"
