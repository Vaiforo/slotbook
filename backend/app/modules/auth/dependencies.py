import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import DomainError
from app.models import Session, User
from app.modules.auth.security import csrf_for, digest
from app.modules.bookings.repository import database_time


def check_origin(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        raise DomainError(403, "forbidden", "Origin is not allowed")


@dataclass
class UserContext:
    db: AsyncSession
    session: Session
    user: User
    csrf: str


async def user_context(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Depends(APIKeyCookie(name="session", auto_error=False))],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AsyncIterator[UserContext]:
    if token is None or len(token) != 43:
        raise DomainError(401, "unauthorized", "Authentication required")
    # Own the transaction before the first SELECT, including all downstream writes.
    async with db.begin():
        session = await db.scalar(
            select(Session).where(Session.token_hash == digest(token)).with_for_update()
        )
        if session is None or session.expires_at <= await database_time(db):
            raise DomainError(401, "unauthorized", "Authentication required")
        csrf = csrf_for(token)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            check_origin(request)
            supplied = csrf_header or ""
            if not secrets.compare_digest(digest(supplied), session.csrf_token_hash):
                raise DomainError(403, "forbidden", "Invalid CSRF token")
        user = await db.get(User, session.user_id)
        if user is None or not user.is_active:
            raise DomainError(401, "unauthorized", "Authentication required")
        yield UserContext(db, session, user, csrf)


CurrentUser = Annotated[UserContext, Depends(user_context, scope="function")]


async def specialist_context(user: CurrentUser) -> UserContext:
    if user.user.role != "specialist":
        raise DomainError(403, "forbidden", "Specialist role required")
    return user


async def client_context(user: CurrentUser) -> UserContext:
    if user.user.role != "client":
        raise DomainError(403, "forbidden", "Client role required")
    return user


SpecialistUser = Annotated[UserContext, Depends(specialist_context)]
ClientUser = Annotated[UserContext, Depends(client_context)]
