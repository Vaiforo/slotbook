from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import func, select

from app.core.errors import DomainError, ErrorResponse
from app.models import Booking, Slot, Specialist
from app.modules.auth.dependencies import ClientUser
from app.modules.bookings.schemas import BookingDetails
from app.modules.bookings.service import BookingService, details

router = APIRouter(
    prefix="/api/v1/me/bookings",
    tags=["client-bookings"],
    responses={c: {"model": ErrorResponse} for c in (401, 403, 404, 409)},
)


class ClientBooking(BookingDetails):
    specialist_name: str
    specialist_slug: str
    specialization: str
    timezone: str
    workplace: str
    service_area: str
    work_formats: str


class ClientBookingPage(BaseModel):
    items: list[ClientBooking]
    total: int
    upcoming_count: int
    limit: int
    offset: int


@router.get("", response_model=ClientBookingPage)
async def my_bookings(
    client: ClientUser,
    view: Literal["upcoming", "past", "cancelled"] = "upcoming",
    from_: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    to: AwareDatetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
) -> ClientBookingPage:
    if from_ and to and from_ >= to:
        raise DomainError(422, "invalid_range", "Start must precede end")
    conditions = [Booking.client_user_id == client.user.id]
    if view == "cancelled":
        conditions.append(Booking.status == "cancelled")
    else:
        conditions.append(Booking.status == "confirmed")
        conditions.append(
            Slot.ends_at > func.now() if view == "upcoming" else Slot.ends_at <= func.now()
        )
    if from_:
        conditions.append(Slot.starts_at >= from_)
    if to:
        conditions.append(Slot.starts_at < to)
    total = await client.db.scalar(
        select(func.count()).select_from(Booking).join(Slot).where(*conditions)
    )
    upcoming = await client.db.scalar(
        select(func.count())
        .select_from(Booking)
        .join(Slot)
        .where(
            Booking.client_user_id == client.user.id,
            Booking.status == "confirmed",
            Slot.ends_at > func.now(),
        )
    )
    rows = await client.db.execute(
        select(Booking, Slot, Specialist)
        .join(Slot, Slot.id == Booking.slot_id)
        .join(Specialist, Specialist.id == Slot.specialist_id)
        .where(*conditions)
        .order_by(Slot.starts_at.asc() if view == "upcoming" else Slot.starts_at.desc(), Booking.id)
        .limit(limit)
        .offset(offset)
    )
    return ClientBookingPage(
        items=[
            ClientBooking(
                **details(b, s).model_dump(),
                specialist_name=p.display_name,
                specialist_slug=p.slug,
                specialization=p.specialization,
                timezone=p.timezone,
                workplace=p.workplace,
                service_area=p.service_area,
                work_formats=p.work_formats,
            )
            for b, s, p in rows
        ],
        total=total or 0,
        upcoming_count=upcoming or 0,
        limit=limit,
        offset=offset,
    )


@router.post("/{booking_id}/cancel", response_model=BookingDetails)
async def cancel_own_booking(booking_id: UUID, client: ClientUser) -> BookingDetails:
    return await BookingService(client.db).cancel(booking_id, None, client_user_id=client.user.id)
