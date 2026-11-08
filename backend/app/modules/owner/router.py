from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError, ErrorResponse
from app.models import Booking, Slot, Specialist
from app.modules.bookings.repository import database_time, has_confirmed_booking
from app.modules.bookings.service import details
from app.modules.owner.dependencies import Owner
from app.modules.owner.schemas import (
    BookingFilters,
    OwnerBookings,
    OwnerSlot,
    OwnerSlots,
    ScheduleSlot,
    SlotCreate,
    SlotUpdate,
)
from app.modules.specialists.schemas import SlotFilters

router = APIRouter(
    prefix="/api/v1",
    tags=["owner"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 409)},
)


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


@router.get("/me/slots", response_model=OwnerSlots, operation_id="owner_slots")
async def slots(filters: Annotated[SlotFilters, Query()], owner: Owner) -> OwnerSlots:
    occupied = (
        select(Booking.id).where(Booking.slot_id == Slot.id, Booking.status == "confirmed").exists()
    )
    rows = await owner.db.execute(
        select(Slot, occupied)
        .join(Specialist, Slot.specialist_id == Specialist.id)
        .where(
            Specialist.user_id == owner.user.id,
            Slot.starts_at >= filters.from_,
            Slot.starts_at < filters.to,
        )
        .order_by(Slot.starts_at, Slot.id)
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return OwnerSlots(
        items=[
            ScheduleSlot(**OwnerSlot.model_validate(slot).model_dump(), has_booking=booked)
            for slot, booked in rows
        ],
        limit=filters.limit,
        offset=filters.offset,
    )
