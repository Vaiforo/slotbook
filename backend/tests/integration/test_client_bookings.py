from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from client_auth import authenticate_client
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from test_accounts import account_api  # noqa: F401

from app.models import Booking, Slot, Specialist, User


@pytest.mark.asyncio
async def test_account_ownership_snapshot_cancel_and_guest_access(account_api):  # noqa: F811
    app, client = account_api
    await authenticate_client(client, email=f"{uuid4()}@example.com", name="Account name")
    async with app.state.session_factory.begin() as db:
        user = User(
            normalized_email=f"{uuid4()}@example.com", password_hash="!disabled", role="specialist"
        )
        db.add(user)
        await db.flush()
        specialist = Specialist(
            user_id=user.id,
            slug=str(uuid4()),
            display_name="Specialist",
            publication_status="published",
        )
        db.add(specialist)
        await db.flush()
        start = datetime.now(UTC) + timedelta(days=1)
        slot = Slot(
            specialist_id=specialist.id, starts_at=start, ends_at=start + timedelta(minutes=30)
        )
        db.add(slot)
        await db.flush()
        slot_id = str(slot.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=client.base_url) as other:
        assert (await other.post("/api/v1/bookings", json={"slot_id": slot_id})).status_code == 401
        await authenticate_client(other, email=f"{uuid4()}@example.com")
        created = await client.post(
            "/api/v1/bookings",
            json={
                "slot_id": slot_id,
                "client_name": "Forged name",
                "client_email": "fake@example.com",
            },
        )
        assert created.status_code == 201, created.text
        booking = created.json()
        assert booking["client_name"] == "Account name"
        assert booking["client_email"] != "fake@example.com"
        mine = (await client.get("/api/v1/me/bookings")).json()
        assert mine["upcoming_count"] == 1
        assert mine["items"][0]["specialist_name"] == "Specialist"
        assert (await other.get("/api/v1/me/bookings")).json()["total"] == 0
        assert (await other.post(f"/api/v1/me/bookings/{booking['id']}/cancel")).status_code == 404
        assert (await client.post(f"/api/v1/me/bookings/{booking['id']}/cancel")).status_code == 200
        assert (await client.post(f"/api/v1/me/bookings/{booking['id']}/cancel")).status_code == 200
        assert (await client.get("/api/v1/me/bookings")).json()["total"] == 0
        assert (await client.get("/api/v1/me/bookings?view=cancelled")).json()["total"] == 1
        async with app.state.session_factory() as db:
            saved = await db.scalar(select(Booking).where(Booking.id == booking["id"]))
            assert saved.client_user_id is not None
