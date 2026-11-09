import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def worker(url, prefix):
    async def run():
        app = create_app(
            Settings(_env_file=None, redis_url=url, rate_prefix=prefix, booking_limit=7)
        )
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                return [
                    r.status_code
                    for r in await asyncio.gather(
                        *[client.post("/api/v1/bookings", json={}) for _ in range(10)]
                    )
                ]

    return asyncio.run(run())


@pytest.fixture
def redis_url():
    url = os.getenv("SLOTBOOK_TEST_REDIS_URL")
    if not url:
        pytest.skip("SLOTBOOK_TEST_REDIS_URL is required")
    return url


def test_two_processes_share_atomic_budget(redis_url):
    prefix = "slotbook-test:" + uuid4().hex
    with ProcessPoolExecutor(2, mp_context=get_context("spawn")) as pool:
        jobs = [pool.submit(worker, redis_url, prefix) for _ in range(2)]
        codes = [code for job in jobs for code in job.result(timeout=30)]
    assert codes.count(401) == 7
    assert codes.count(429) == 13


@pytest.mark.asyncio
async def test_expiry_ip_isolation_and_no_forwarded_header_spoofing(redis_url):
    app = create_app(
        Settings(
            _env_file=None,
            redis_url=redis_url,
            rate_prefix="slotbook-test:" + uuid4().hex,
            login_limit=1,
            booking_limit=1,
            rate_window_seconds=1,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/api/v1/bookings", json={})).status_code == 401
            response = await client.post(
                "/api/v1/bookings/", json={}, headers={"X-Forwarded-For": "different"}
            )
            assert response.status_code == 429
            assert response.headers["Retry-After"] == "1"
            assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
            assert response.headers["Cache-Control"] == "no-store"
            assert (await client.post("/api/v1/auth/login", json={})).status_code == 422
            assert (await client.post("/api/v1/auth/login", json={})).status_code == 429
            async with AsyncClient(
                transport=ASGITransport(app=app, client=("192.0.2.5", 1000)), base_url="http://test"
            ) as other:
                assert (await other.post("/api/v1/bookings", json={})).status_code == 401
            await asyncio.sleep(1.1)
            assert (await client.post("/api/v1/bookings", json={})).status_code == 401


@pytest.mark.asyncio
async def test_redis_failure_blocks_writes_but_not_liveness():
    app = create_app(Settings(_env_file=None, redis_url="redis://127.0.0.1:1/0"))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in [
                "/api/v1/auth/login",
                "/api/v1/bookings",
                "/api/v1/specialists/fixture/search",
            ]:
                response = await client.post(path, json={})
                assert response.status_code == 503
                assert response.json()["error"]["code"] == "rate_limit_unavailable"
                assert response.headers["Retry-After"] == "5"
            assert (await client.get("/health/live")).status_code == 200


def test_production_requires_redis():
    with pytest.raises(ValueError, match="redis_url"):
        Settings(_env_file=None, environment="production", public_origin="https://example.com")


@pytest.mark.asyncio
async def test_ai_limit_is_shared_across_specialists(redis_url):
    app = create_app(
        Settings(
            _env_file=None,
            redis_url=redis_url,
            rate_prefix="slotbook-test:" + uuid4().hex,
            ai_limit=1,
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (
                await client.post("/api/v1/specialists/fixture/search", json={})
            ).status_code == 422
            response = await client.post("/api/v1/specialists/other/search/", json={})
            assert response.status_code == 429
            assert int(response.headers["Retry-After"]) > 0
            assert (await client.get("/health/live")).status_code == 200
