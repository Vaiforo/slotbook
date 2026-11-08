import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models import Session, Specialist, User

ORIGIN = "https://slotbook.example"
PASSWORD = " account-password-with-spaces "


@pytest_asyncio.fixture
async def account_api(database):
    app = create_app(Settings(database_url=database, environment="test", public_origin=ORIGIN))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            yield app, client


def registration(role="client"):
    return dict(
        email=f"{uuid4()}@example.com",
        password=PASSWORD,
        full_name="Анна Иванова",
        role=role,
        timezone="Asia/Omsk",
        category_code="medicine" if role == "specialist" else None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["client", "specialist"])
async def test_registration_profile_roles_and_password(account_api, role):
    app, client = account_api
    data = registration(role)
    response = await client.post("/api/v1/auth/register", json=data, headers={"Origin": ORIGIN})
    assert response.status_code == 201, response.text
    identity = response.json()
    assert identity["role"] == role
    assert (identity["specialist"] is not None) == (role == "specialist")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    headers = {"Origin": ORIGIN, "X-CSRF-Token": identity["csrf_token"]}
    assert (await client.get("/api/v1/auth/me")).json() == identity
    async with app.state.session_factory() as db:
        user = await db.get(User, identity["id"])
        assert user.password_hash != PASSWORD
        if role == "specialist":
            specialist = await db.scalar(select(Specialist).where(Specialist.user_id == user.id))
            assert specialist.publication_status == "draft"
            assert specialist.category_code == "medicine"
    profile = dict(full_name="Новое имя", phone="+7 900 000 00 00", timezone="UTC")
    assert (await client.patch("/api/v1/me/profile", json=profile)).status_code == 403
    updated = await client.patch("/api/v1/me/profile", json=profile, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["full_name"] == profile["full_name"]
    assert (
        await client.patch(
            "/api/v1/me/profile", json={**profile, "role": "specialist"}, headers=headers
        )
    ).status_code == 422
    if role == "client":
        assert (await client.get("/api/v1/me/slots")).status_code == 403
        assert (await client.post("/api/v1/slots", json={}, headers=headers)).status_code == 403
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json=dict(current_password="wrong", new_password="new-password-123"),
    )
    assert changed.status_code == 400
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json=dict(current_password=PASSWORD, new_password="new-password-123"),
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    async with app.state.session_factory() as db:
        assert not (
            await db.scalars(select(Session).where(Session.user_id == identity["id"]))
        ).all()
    for password, status in [(PASSWORD, 401), ("new-password-123", 204)]:
        assert (
            await client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json=dict(email=data["email"].upper(), password=password),
            )
        ).status_code == status


@pytest.mark.asyncio
async def test_registration_validation_and_concurrency(account_api):
    app, client = account_api
    data = registration()
    assert (await client.post("/api/v1/auth/register", json=data)).status_code == 403
    for changes in [
        dict(role="admin"),
        dict(full_name="  "),
        dict(password="short"),
        dict(timezone="Unknown/Nowhere"),
        dict(role="specialist"),
        dict(category_code="medicine"),
        dict(email="not-email"),
    ]:
        response = await client.post(
            "/api/v1/auth/register", headers={"Origin": ORIGIN}, json={**data, **changes}
        )
        assert response.status_code == 422, response.text

    async def create():
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as other:
            return await other.post("/api/v1/auth/register", json=data, headers={"Origin": ORIGIN})

    responses = await asyncio.gather(create(), create())
    assert sorted(r.status_code for r in responses) == [201, 409]
