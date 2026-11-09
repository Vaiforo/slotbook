from httpx import ASGITransport, AsyncClient


async def authenticate_client(client, *, email="client@example.com", name="Анна Тестовая"):
    app = client._transport.app
    origin = app.state.settings.public_origin
    data = dict(
        email=email, full_name=name, password="test-client-password", role="client", timezone="UTC"
    )
    response = await client.post("/api/v1/auth/register", headers={"Origin": origin}, json=data)
    if response.status_code == 409:
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": origin},
            json=dict(email=email, password="test-client-password"),
        )
        assert response.status_code == 204, response.text
        response = await client.get("/api/v1/auth/me")
    assert response.status_code in (200, 201), response.text
    client.headers.update({"Origin": origin, "X-CSRF-Token": response.json()["csrf_token"]})


async def book_as_client(client, *, json):
    async with AsyncClient(
        transport=ASGITransport(app=client._transport.app), base_url=client.base_url
    ) as actor:
        await authenticate_client(
            actor,
            email=json.get("client_email", "client@example.com"),
            name=json.get("client_name", "Client"),
        )
        return await actor.post("/api/v1/bookings", json=json)
