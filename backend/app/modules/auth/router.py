import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.db import get_session
from app.core.errors import DomainError, ErrorResponse
from app.models import Session, Specialist, User
from app.modules.auth.dependencies import CurrentUser as Owner
from app.modules.auth.dependencies import check_origin
from app.modules.auth.schemas import ChangePassword, Identity, Login, ProfileUpdate, Register
from app.modules.auth.security import DUMMY_HASH, csrf_for, digest, hasher, verify_password
from app.modules.bookings.repository import database_time
from app.modules.specialists.schemas import PublicSpecialist

router = APIRouter(
    prefix="/api/v1",
    tags=["auth"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 409)},
)


@router.post(
    "/auth/register",
    status_code=201,
    response_model=Identity,
    responses={
        409: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def register(
    data: Register,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Identity:
    check_origin(request)
    encoded = await run_in_threadpool(hasher.hash, data.password)
    token = secrets.token_urlsafe(32)
    try:
        async with db.begin():
            user = User(
                normalized_email=str(data.email).strip().lower(),
                password_hash=encoded,
                role=data.role,
                full_name=data.full_name,
                phone=data.phone,
                timezone=data.timezone,
            )
            db.add(user)
            await db.flush()
            specialist = None
            if data.role == "specialist":
                specialist = Specialist(
                    user_id=user.id,
                    slug="specialist-" + user.id.hex,
                    display_name=user.full_name,
                    timezone=user.timezone,
                    category_code=data.category_code,
                )
                db.add(specialist)
                await db.flush()
            old = request.cookies.get("session")
            if old:
                await db.execute(delete(Session).where(Session.token_hash == digest(old)))
            db.add(
                Session(
                    user_id=user.id,
                    token_hash=digest(token),
                    csrf_token_hash=digest(csrf_for(token)),
                    expires_at=await database_time(db) + timedelta(hours=12),
                )
            )
            identity = Identity(
                id=user.id,
                email=user.normalized_email,
                role=user.role,
                full_name=user.full_name,
                phone=user.phone,
                timezone=user.timezone,
                csrf_token=csrf_for(token),
                specialist=PublicSpecialist.model_validate(specialist) if specialist else None,
            )
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505" and "normalized_email" in str(
            getattr(getattr(exc.orig, "diag", None), "constraint_name", "")
        ):
            raise DomainError(409, "email_exists", "Email is already registered") from None
        raise
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=request.app.state.settings.public_origin.startswith("https://"),
        samesite="lax",
        max_age=43200,
        path="/",
    )
    return identity


@router.get("/me/profile", response_model=Identity)
async def profile(owner: Owner) -> Identity:
    return await me(owner)


@router.patch("/me/profile", response_model=Identity)
async def update_profile(data: ProfileUpdate, owner: Owner) -> Identity:
    owner.user.full_name = data.full_name
    owner.user.phone = data.phone
    owner.user.timezone = data.timezone
    await owner.db.flush()
    return await me(owner)


@router.post("/auth/change-password", status_code=204)
async def change_password(data: ChangePassword, owner: Owner, request: Request) -> Response:
    if not await run_in_threadpool(
        verify_password, data.current_password, owner.user.password_hash
    ):
        raise DomainError(400, "invalid_password", "Current password is incorrect")
    owner.user.password_hash = await run_in_threadpool(hasher.hash, data.new_password)
    await owner.db.execute(delete(Session).where(Session.user_id == owner.user.id))
    response = Response(status_code=204)
    response.delete_cookie(
        "session",
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.public_origin.startswith("https://"),
    )
    return response


@router.post(
    "/auth/login",
    status_code=204,
    operation_id="login",
    responses={code: {"model": ErrorResponse} for code in (429, 503)},
)
async def login(
    data: Login, request: Request, db: Annotated[AsyncSession, Depends(get_session)]
) -> Response:
    check_origin(request)
    async with db.begin():
        user = await db.scalar(
            select(User).where(User.normalized_email == data.email.strip().lower())
        )
        encoded = (
            user.password_hash if user and user.password_hash.startswith("$argon2") else DUMMY_HASH
        )
        valid = await run_in_threadpool(verify_password, data.password, encoded)
        if not valid or user is None or not user.is_active or encoded == DUMMY_HASH:
            raise DomainError(401, "unauthorized", "Invalid email or password")
        old = request.cookies.get("session")
        if old:
            await db.execute(delete(Session).where(Session.token_hash == digest(old)))
        token = secrets.token_urlsafe(32)
        db.add(
            Session(
                user_id=user.id,
                token_hash=digest(token),
                csrf_token_hash=digest(csrf_for(token)),
                expires_at=await database_time(db) + timedelta(hours=12),
            )
        )
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = await run_in_threadpool(hasher.hash, data.password)
    response = Response(status_code=204)
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=request.app.state.settings.public_origin.startswith("https://"),
        samesite="lax",
        max_age=43200,
        path="/",
    )
    return response


@router.get("/auth/me", response_model=Identity, operation_id="current_owner")
async def me(owner: Owner) -> Identity:
    specialist = await owner.db.scalar(
        select(Specialist).where(Specialist.user_id == owner.user.id)
    )
    return Identity(
        id=owner.user.id,
        email=owner.user.normalized_email,
        role=owner.user.role,
        full_name=owner.user.full_name,
        phone=owner.user.phone,
        timezone=owner.user.timezone,
        csrf_token=owner.csrf,
        specialist=PublicSpecialist.model_validate(specialist) if specialist else None,
    )


@router.post("/auth/logout", status_code=204, operation_id="logout")
async def logout(owner: Owner, request: Request) -> Response:
    await owner.db.delete(owner.session)
    response = Response(status_code=204)
    response.delete_cookie(
        "session",
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.app.state.settings.public_origin.startswith("https://"),
    )
    return response
