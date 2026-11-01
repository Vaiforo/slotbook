from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session
from test_bookings import api as booking_api  # noqa: F401
from test_bookings import headers, payload

from app.models import Booking, NotificationDelivery, OutboxEvent
from app.notifications.delivery import deliver
from app.notifications.dispatcher import dispatch_one


def events(url, booking_id):
    engine = create_engine(url)
    with Session(engine) as db:
        result = list(db.scalars(select(OutboxEvent).where(OutboxEvent.booking_id == booking_id)))
    engine.dispose()
    return result


@pytest.mark.asyncio
async def test_event_commit_rollback_and_cancel_idempotency(booking_api, database, monkeypatch):  # noqa: F811
    from app.modules.bookings import service

    app, client, new_slot, _ = booking_api
    slot = await new_slot()
    original = service.details

    def broken(*args):
        raise RuntimeError("rollback after event flush")

    monkeypatch.setattr(service, "details", broken)
    assert (await client.post("/api/v1/bookings", json=payload(slot))).status_code == 500
    async with app.state.session_factory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Booking).where(Booking.slot_id == slot)
            )
            == 0
        )
        # No orphan events can survive the failed booking transaction.
        assert await db.scalar(select(func.count()).select_from(OutboxEvent)) == 0
    monkeypatch.setattr(service, "details", original)
    created = (await client.post("/api/v1/bookings", json=payload(slot))).json()
    assert len(events(database, UUID(created["id"]))) == 1
    for _ in range(2):
        assert (
            await client.post(f"/api/v1/bookings/{created['id']}/cancel", headers=headers(created))
        ).status_code == 200
    assert sorted(e.kind for e in events(database, UUID(created["id"]))) == [
        "booking_cancelled",
        "booking_created",
    ]


@pytest.mark.asyncio
async def test_broker_failure_redelivery_and_provider_idempotency(booking_api, database):  # noqa: F811
    app, client, new_slot, _ = booking_api
    created = (await client.post("/api/v1/bookings", json=payload(await new_slot()))).json()
    event = events(database, UUID(created["id"]))[0]
    engine = create_engine(database)

    def unavailable(event_id):
        raise ConnectionError("broker down")

    with pytest.raises(ConnectionError):
        dispatch_one(engine, unavailable)
    with Session(engine) as db:
        assert db.get(OutboxEvent, event.id).published_at is None
    published = []
    assert dispatch_one(engine, published.append)
    # Simulate publisher-confirm followed by DB rollback: same event may be published again.
    with Session(engine) as db, db.begin():
        db.execute(
            update(OutboxEvent).where(OutboxEvent.id == event.id).values(next_publish_at=func.now())
        )
    while str(event.id) not in published:
        assert dispatch_one(engine, published.append)
    received = []

    def provider(request):
        received.append(request.headers["Idempotency-Key"])
        assert "manage_token" not in request.content.decode()
        return httpx.Response(202)

    settings = app.state.settings.model_copy(update={"email_url": "https://mail.invalid/messages"})
    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        assert deliver(engine, settings, event.id, http) == "sent"
        assert deliver(engine, settings, event.id, http) == "ignored"
    assert received == [str(event.id)]
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,retryable", [(429, True), (503, True), (400, False), ("timeout", True)]
)
async def test_provider_errors_and_retry_exhaustion(booking_api, database, failure, retryable):  # noqa: F811
    app, client, new_slot, _ = booking_api
    created = (await client.post("/api/v1/bookings", json=payload(await new_slot()))).json()
    event = events(database, UUID(created["id"]))[0]
    settings = app.state.settings.model_copy(
        update={"email_url": "https://mail.invalid/messages", "notification_max_attempts": 2}
    )
    engine = create_engine(database)

    def provider(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private provider detail")
        return httpx.Response(failure, headers={"Retry-After": "90"})

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        assert deliver(engine, settings, event.id, http) == ("retrying" if retryable else "failed")
        with Session(engine) as db, db.begin():
            row = db.get(NotificationDelivery, (event.id, "email"))
            assert row.attempts == 1
            assert "private" not in row.last_error
            if failure in [429, 503]:
                assert row.next_attempt_at >= event.created_at + timedelta(seconds=85)
            row.next_attempt_at = func.now()
        assert deliver(engine, settings, event.id, http) == ("failed" if retryable else "ignored")
    engine.dispose()


@pytest.mark.asyncio
async def test_provider_success_before_commit_may_be_repeated(booking_api, database):  # noqa: F811
    from sqlalchemy import event as sql_event

    app, client, new_slot, _ = booking_api
    created = (await client.post("/api/v1/bookings", json=payload(await new_slot()))).json()
    event = events(database, UUID(created["id"]))[0]
    engine = create_engine(database)
    settings = app.state.settings.model_copy(update={"email_url": "https://mail.invalid/messages"})
    calls, receipts = [], set()

    def provider(request):
        key = request.headers["Idempotency-Key"]
        calls.append(key)
        receipts.add(key)  # A provider with idempotency accepts the event only once.
        return httpx.Response(202)

    def fail_commit(connection):
        raise RuntimeError("crash after external acceptance")

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        sql_event.listen(engine, "commit", fail_commit)
        with pytest.raises(RuntimeError):
            deliver(engine, settings, event.id, http)
        sql_event.remove(engine, "commit", fail_commit)
        assert deliver(engine, settings, event.id, http) == "sent"
    assert calls == [str(event.id), str(event.id)]
    assert receipts == {str(event.id)}
    engine.dispose()
