import os
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.models import Booking, Slot, Specialist, User
from scripts.seed_demo import DEMO_SPECIALIST, seed_demo

pytestmark = pytest.mark.skipif(
    not os.getenv("SLOTBOOK_TEST_ADMIN_URL"),
    reason="Set SLOTBOOK_TEST_ADMIN_URL to a PostgreSQL 18 instance allowing CREATE DATABASE",
)


@pytest.fixture
def connection(database):
    engine = create_engine(database)
    with engine.connect() as conn:
        tx = conn.begin()
        user = conn.scalar(
            insert(User)
            .values(normalized_email=f"{uuid4()}@example.invalid", password_hash="!disabled")
            .returning(User.id)
        )
        specialist = conn.scalar(
            insert(Specialist)
            .values(user_id=user, slug=str(uuid4()), display_name="Test", timezone="Asia/Omsk")
            .returning(Specialist.id)
        )
        yield conn, specialist
        tx.rollback()
    engine.dispose()


def slot(specialist, start=None, **changes):
    start = start or datetime(2030, 1, 1, 10, tzinfo=ZoneInfo("Asia/Omsk"))
    return dict(
        specialist_id=specialist, starts_at=start, ends_at=start + timedelta(minutes=30), **changes
    )


def reject(conn, statement, constraint):
    with pytest.raises(IntegrityError) as exc:
        with conn.begin_nested():
            conn.execute(statement)
    assert exc.value.orig.diag.constraint_name == constraint


def test_overlaps_adjacency_and_different_specialists(connection):
    conn, specialist = connection
    values = slot(specialist)
    conn.execute(insert(Slot).values(**values))
    reject(
        conn,
        insert(Slot).values(**slot(specialist, values["starts_at"] + timedelta(minutes=15))),
        "no_overlapping_slots",
    )
    reject(conn, insert(Slot).values(**slot(specialist, state="closed")), "no_overlapping_slots")
    conn.execute(insert(Slot).values(**slot(specialist, values["ends_at"])))
    other_user = conn.scalar(
        insert(User)
        .values(normalized_email="other@example.invalid", password_hash="!disabled")
        .returning(User.id)
    )
    other = conn.scalar(
        insert(Specialist)
        .values(user_id=other_user, slug="other", display_name="Other")
        .returning(Specialist.id)
    )
    conn.execute(insert(Slot).values(**slot(other)))
    saved = conn.execute(
        select(Slot.starts_at, Slot.ends_at).where(Slot.specialist_id == specialist)
    ).first()
    assert saved.starts_at == values["starts_at"]
    assert saved.starts_at.tzinfo is not None
    assert (
        conn.scalar(select(Specialist.timezone).where(Specialist.id == specialist)) == "Asia/Omsk"
    )


def test_booking_unique_and_cancellation_history(connection):
    conn, specialist = connection
    slot_id = conn.scalar(insert(Slot).values(**slot(specialist)).returning(Slot.id))
    values = dict(
        slot_id=slot_id,
        client_name="Test",
        client_email="test@example.invalid",
        manage_token_hash="a" * 64,
    )
    booking = conn.scalar(insert(Booking).values(**values).returning(Booking.id))
    values["manage_token_hash"] = "b" * 64
    reject(conn, insert(Booking).values(**values), "one_confirmed_booking_per_slot")
    conn.execute(
        Booking.__table__.update()
        .where(Booking.id == booking)
        .values(status="cancelled", cancelled_at=func.now())
    )
    conn.execute(insert(Booking).values(**values))
    assert conn.scalar(select(func.count()).select_from(Booking)) == 2


@pytest.mark.parametrize(
    "field,value,constraint",
    [
        ("state", "invalid", "slot_state"),
        ("ends_at", datetime(2030, 1, 1, 11, tzinfo=ZoneInfo("Asia/Omsk")), "slot_duration"),
        ("specialist_id", uuid4(), "slots_specialist_id_fkey"),
    ],
)
def test_slot_constraints(connection, field, value, constraint):
    conn, specialist = connection
    values = slot(specialist)
    values[field] = value
    reject(conn, insert(Slot).values(**values), constraint)


def test_not_null_and_booking_state(connection):
    conn, specialist = connection
    with pytest.raises(IntegrityError) as exc:
        with conn.begin_nested():
            conn.execute(insert(Slot).values(**slot(specialist), state=None))
    assert exc.value.orig.sqlstate == "23502"
    slot_id = conn.scalar(insert(Slot).values(**slot(specialist)).returning(Slot.id))
    base = dict(
        slot_id=slot_id,
        client_name="Test",
        client_email="t@example.invalid",
        manage_token_hash="c" * 64,
    )
    reject(conn, insert(Booking).values(**base, status="cancelled"), "booking_cancellation_state")
    # Invalid status also violates cancellation consistency (checked first by PostgreSQL).
    reject(conn, insert(Booking).values(**base, status="invalid"), "booking_cancellation_state")


def test_seed_idempotency_and_future_dates(database):
    seed_demo(database)
    engine = create_engine(database)
    with engine.connect() as conn:
        first = conn.execute(
            select(Slot.id, Slot.starts_at)
            .where(Slot.specialist_id == DEMO_SPECIALIST)
            .order_by(Slot.starts_at)
        ).all()
    seed_demo(database)
    with engine.connect() as conn:
        second = conn.execute(
            select(Slot.id, Slot.starts_at)
            .where(Slot.specialist_id == DEMO_SPECIALIST)
            .order_by(Slot.starts_at)
        ).all()
        assert first == second
        assert len(second) == 4
        assert all(row.starts_at > conn.scalar(select(func.now())) for row in second)
        assert conn.scalar(select(func.count()).select_from(User)) == 1
        assert conn.scalar(select(func.count()).select_from(Specialist)) == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_async_sessions_are_isolated_and_rollback(database):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(database)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = f"{uuid4()}@example.invalid"
    try:
        async with factory() as writer, factory() as reader:
            await writer.execute(
                insert(User).values(normalized_email=email, password_hash="!disabled")
            )
            query = select(User.id).where(User.normalized_email == email)
            assert await writer.scalar(query) is not None
            assert await reader.scalar(query) is None
            await writer.rollback()
            assert await reader.scalar(query) is None
    finally:
        await engine.dispose()
