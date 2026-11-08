import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from test_accounts import ORIGIN, PASSWORD, account_api, registration  # noqa: F401

import app.modules.auth.router as auth


@pytest.mark.asyncio
async def test_delayed_login_cannot_recreate_session_after_password_change(
    account_api,  # noqa: F811
    monkeypatch,
):
    app, owner = account_api
    data = registration()
    registered = await owner.post("/api/v1/auth/register", json=data, headers={"Origin": ORIGIN})
    entered, release = asyncio.Event(), asyncio.Event()
    original = auth.run_in_threadpool
    paused = False

    async def gate(function, *args, **kwargs):
        nonlocal paused
        result = await original(function, *args, **kwargs)
        if function is auth.verify_password and not paused:
            paused = True
            entered.set()
            await release.wait()
        return result

    monkeypatch.setattr(auth, "run_in_threadpool", gate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as other:
        login = asyncio.create_task(
            other.post(
                "/api/v1/auth/login",
                json={"email": data["email"], "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
        )
        await asyncio.wait_for(entered.wait(), 5)
        try:
            changed = await owner.post(
                "/api/v1/auth/change-password",
                json={"current_password": PASSWORD, "new_password": "new-review-password"},
                headers={"Origin": ORIGIN, "X-CSRF-Token": registered.json()["csrf_token"]},
            )
            assert changed.status_code == 204
        finally:
            release.set()
        assert (await login).status_code == 401
        assert (await other.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_password_change_from_two_sessions_is_serialized(account_api, monkeypatch):  # noqa: F811
    app, first = account_api
    data = registration()
    registered = await first.post("/api/v1/auth/register", json=data, headers={"Origin": ORIGIN})
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as second:
        assert (
            await second.post(
                "/api/v1/auth/login",
                json={"email": data["email"], "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
        ).status_code == 204
        identity = (await second.get("/api/v1/auth/me")).json()
        entered, release = asyncio.Event(), asyncio.Event()
        original = auth.run_in_threadpool
        paused = False

        async def gate(function, *args, **kwargs):
            nonlocal paused
            result = await original(function, *args, **kwargs)
            if function is auth.verify_password and not paused:
                paused = True
                entered.set()
                await release.wait()
            return result

        monkeypatch.setattr(auth, "run_in_threadpool", gate)

        async def change(client, csrf):
            return await client.post(
                "/api/v1/auth/change-password",
                json={"current_password": PASSWORD, "new_password": "new-review-password"},
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
            )

        request_one = asyncio.create_task(change(first, registered.json()["csrf_token"]))
        await asyncio.wait_for(entered.wait(), 5)
        request_two = asyncio.create_task(change(second, identity["csrf_token"]))
        release.set()
        results = await asyncio.wait_for(asyncio.gather(request_one, request_two), 10)
        assert [r.status_code for r in results] == [204, 401]
