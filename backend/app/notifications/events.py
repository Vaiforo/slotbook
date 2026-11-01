from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, NotificationDelivery, OutboxEvent


async def enqueue(session: AsyncSession, booking: Booking, kind: str) -> None:
    event = OutboxEvent(id=uuid4(), booking_id=booking.id, kind=kind)
    session.add(event)
    await session.flush()
    session.add(NotificationDelivery(event_id=event.id, channel="email"))
    await session.flush()
