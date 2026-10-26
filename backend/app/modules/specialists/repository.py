from collections.abc import Sequence

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Slot, Specialist
from app.modules.specialists.schemas import SlotFilters


async def find_specialist(session: AsyncSession, slug: str) -> Specialist | None:
    result = await session.scalars(select(Specialist).where(Specialist.slug == slug))
    return result.one_or_none()


async def available_slots(
    session: AsyncSession, specialist: Specialist, filters: SlotFilters
) -> Sequence[Slot]:
    booked = exists().where(Booking.slot_id == Slot.id, Booking.status == "confirmed")
    result = await session.scalars(
        select(Slot)
        .where(
            Slot.specialist_id == specialist.id,
            Slot.state == "open",
            Slot.starts_at > func.now(),
            Slot.starts_at >= filters.from_,
            Slot.starts_at < filters.to,
            ~booked,
        )
        .order_by(Slot.starts_at, Slot.id)
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return result.all()
