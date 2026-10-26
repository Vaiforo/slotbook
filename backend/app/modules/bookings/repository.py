from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Slot


async def get_slot(session: AsyncSession, slot_id: UUID, *, lock: bool = False) -> Slot | None:
    query = select(Slot).where(Slot.id == slot_id).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


async def get_booking(
    session: AsyncSession, booking_id: UUID, *, lock: bool = False
) -> Booking | None:
    query = (
        select(Booking).where(Booking.id == booking_id).execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


async def has_confirmed_booking(session: AsyncSession, slot_id: UUID) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(Booking.slot_id == slot_id, Booking.status == "confirmed"))
        )
    )


async def database_time(session: AsyncSession) -> datetime:
    # now()/CURRENT_TIMESTAMP is the transaction start, BEFORE a possible lock wait.
    return cast(datetime, (await session.scalars(select(func.clock_timestamp()))).one())
