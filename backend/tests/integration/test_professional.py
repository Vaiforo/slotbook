from datetime import UTC, datetime, timedelta

import pytest
from client_auth import book_as_client
from test_accounts import ORIGIN, account_api, registration  # noqa: F401


@pytest.mark.asyncio
async def test_publish_catalog_services_shifts_and_unpublish(account_api):  # noqa: F811
    _, client = account_api
    registered = await client.post(
        "/api/v1/auth/register", json=registration("specialist"), headers={"Origin": ORIGIN}
    )
    assert registered.status_code == 201, registered.text
    identity = registered.json()
    headers = {"Origin": ORIGIN, "X-CSRF-Token": identity["csrf_token"]}
    slug = identity["specialist"]["slug"]
    assert (await client.get(f"/api/v1/specialists/{slug}")).status_code == 404
    assert (await client.post("/api/v1/me/specialist/publish", headers=headers)).status_code == 409
    profile = dict(
        display_name="Anna",
        category_code="medicine",
        specialization="Therapist",
        short_description="Consultations",
        description="Detailed description",
        city="Omsk",
        work_formats="online",
        timezone="UTC",
    )
    response = await client.patch("/api/v1/me/specialist", json=profile, headers=headers)
    assert response.status_code == 200, response.text
    assert (
        await client.put(
            "/api/v1/me/specialist/services",
            json={"services": [{"name": "Consultation", "description": "Initial visit"}]},
            headers=headers,
        )
    ).status_code == 200
    assert (await client.post("/api/v1/me/specialist/publish", headers=headers)).status_code == 200
    catalog = (
        await client.get(
            "/api/v1/specialists", params={"q": "Anna", "category": "medicine", "city": "omsk"}
        )
    ).json()
    assert catalog["total"] == 1
    assert catalog["items"][0]["next_available_at"] is None
    public = (await client.get(f"/api/v1/specialists/{slug}")).json()
    assert public["services"][0]["name"] == "Consultation"
    assert not {"email", "phone", "user_id", "password_hash"} & public.keys()
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    shift = dict(
        date_from=tomorrow,
        date_to=tomorrow,
        weekdays=list(range(7)),
        start="09:00",
        end="12:00",
        breaks=[dict(start="10:00", end="11:00")],
    )
    preview = await client.post("/api/v1/me/specialist/slots/preview", headers=headers, json=shift)
    assert preview.json()["count"] == 4
    created = await client.post("/api/v1/me/specialist/slots/batch", headers=headers, json=shift)
    assert created.status_code == 201, created.text
    assert created.json()["count"] == 4
    assert (
        await client.post("/api/v1/me/specialist/slots/batch", headers=headers, json=shift)
    ).status_code == 409
    assert (
        await client.patch(
            "/api/v1/me/specialist", headers=headers, json={**profile, "timezone": "Asia/Omsk"}
        )
    ).status_code == 409
    catalog = (await client.get("/api/v1/specialists", params={"available": True})).json()
    assert catalog["items"][0]["next_available_at"] is not None
    filters = {"from": tomorrow + "T00:00:00Z", "to": tomorrow + "T23:59:59Z"}
    slots = (await client.get(f"/api/v1/specialists/{slug}/slots", params=filters)).json()["items"]
    assert len(slots) == 4
    # A mixed conflicting/new batch must not leave any new intervals behind.
    assert (
        await client.post(
            "/api/v1/me/specialist/slots/batch", headers=headers, json={**shift, "end": "14:00"}
        )
    ).status_code == 409
    assert (
        len((await client.get(f"/api/v1/specialists/{slug}/slots", params=filters)).json()["items"])
        == 4
    )
    booking = await book_as_client(
        client,
        json={
            "slot_id": slots[0]["id"],
            "client_name": "Client",
            "client_email": "client@example.com",
        },
    )
    assert booking.status_code == 201, booking.text
    assert (
        await client.post("/api/v1/me/specialist/unpublish", headers=headers)
    ).status_code == 200
    assert (await client.get("/api/v1/specialists")).json()["total"] == 0
    assert (
        await client.get(f"/api/v1/specialists/{slug}/slots", params=filters)
    ).status_code == 404
    assert (
        await book_as_client(
            client,
            json={
                "slot_id": slots[1]["id"],
                "client_name": "Client",
                "client_email": "client@example.com",
            },
        )
    ).status_code == 409
    # Existing bookings remain manageable after unpublishing.
    booked = booking.json()
    assert (
        await client.get(
            f"/api/v1/bookings/{booked['id']}",
            headers={"Authorization": "Bearer " + booked["manage_token"]},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_client_cannot_manage_professional_account(account_api):  # noqa: F811
    _, client = account_api
    result = await client.post(
        "/api/v1/auth/register", json=registration(), headers={"Origin": ORIGIN}
    )
    headers = {"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]}
    assert (await client.get("/api/v1/me/specialist")).status_code == 403
    assert (await client.post("/api/v1/me/specialist/publish", headers=headers)).status_code == 403
