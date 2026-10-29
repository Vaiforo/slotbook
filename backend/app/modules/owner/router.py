import secrets
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.db import get_session
from app.core.errors import DomainError, ErrorResponse
from app.models import Booking, Session, Slot, Specialist, User
from app.modules.bookings.repository import database_time, has_confirmed_booking
from app.modules.bookings.service import details
from app.modules.owner.dependencies import Owner, check_origin
from app.modules.owner.schemas import (
    BookingFilters,
    Identity,
    Login,
    OwnerBookings,
    OwnerSlot,
    SlotCreate,
    SlotUpdate,
)
from app.modules.owner.security import DUMMY_HASH, csrf_for, digest, hasher, verify_password

router = APIRouter(
    prefix="/api/v1",
    tags=["owner"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 409)},
)


@router.post("/auth/login", status_code=204, operation_id="login")
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
        if not valid or user is None or encoded == DUMMY_HASH:
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
    return Identity(id=owner.user.id, email=owner.user.normalized_email, csrf_token=owner.csrf)


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


async def specialist_id(owner: Owner) -> UUID:
    result = await owner.db.scalar(select(Specialist.id).where(Specialist.user_id == owner.user.id))
    if result is None:
        raise DomainError(404, "not_found", "Not Found")
    return result


@router.post("/slots", status_code=201, response_model=OwnerSlot, operation_id="create_slot")
async def create_slot(data: SlotCreate, owner: Owner) -> OwnerSlot:
    specialist = await specialist_id(owner)
    if data.starts_at <= await database_time(owner.db):
        raise DomainError(409, "slot_started", "Slot must be in the future")
    slot = Slot(specialist_id=specialist, **data.model_dump(), state="open")
    try:
        async with owner.db.begin_nested():
            owner.db.add(slot)
            await owner.db.flush()
    except IntegrityError as exc:
        if (
            getattr(exc.orig, "sqlstate", None) == "23P01"
            and getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "no_overlapping_slots"
        ):
            raise DomainError(409, "slot_overlap", "Slots overlap") from None
        raise
    return OwnerSlot.model_validate(slot)


@router.patch("/slots/{slot_id}", response_model=OwnerSlot, operation_id="update_slot")
async def update_slot(slot_id: UUID, data: SlotUpdate, owner: Owner) -> OwnerSlot:
    specialist = await specialist_id(owner)
    slot = await owner.db.scalar(
        select(Slot)
        .where(Slot.id == slot_id, Slot.specialist_id == specialist)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if slot is None:
        raise DomainError(404, "not_found", "Not Found")
    if slot.starts_at <= await database_time(owner.db):
        raise DomainError(409, "slot_started", "Slot has started")
    if data.state == "closed" and await has_confirmed_booking(owner.db, slot.id):
        raise DomainError(409, "slot_booked", "Slot has a confirmed booking")
    slot.state = data.state
    await owner.db.flush()
    return OwnerSlot.model_validate(slot)


@router.get("/me/bookings", response_model=OwnerBookings, operation_id="owner_bookings")
async def bookings(filters: Annotated[BookingFilters, Query()], owner: Owner) -> OwnerBookings:
    query = (
        select(Booking, Slot)
        .join(Slot, Booking.slot_id == Slot.id)
        .join(Specialist, Slot.specialist_id == Specialist.id)
        .where(
            Specialist.user_id == owner.user.id,
            Slot.starts_at >= filters.from_,
            Slot.starts_at < filters.to,
        )
    )
    if filters.status:
        query = query.where(Booking.status == filters.status)
    rows = await owner.db.execute(
        query.order_by(Slot.starts_at, Booking.id).limit(filters.limit).offset(filters.offset)
    )
    return OwnerBookings(
        items=[details(booking, slot) for booking, slot in rows],
        limit=filters.limit,
        offset=filters.offset,
    )
