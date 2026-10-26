from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # Factory belongs to this app's lifespan/settings; no engine at import time.
    async with request.app.state.session_factory() as session:
        yield session
