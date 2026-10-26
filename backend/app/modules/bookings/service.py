from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.models import Booking, Slot
from app.modules.bookings import repository
from app.modules.bookings.schemas import BookingCreate, BookingCreated, BookingDetails
from app.modules.bookings.security import new_manage_token, token_hash, valid_token


def unavailable() -> DomainError:
    return DomainError(409, "slot_unavailable", "Это время уже недоступно.")


def details(booking: Booking, slot: Slot) -> BookingDetails:
    return BookingDetails.model_validate(
        {
            "id": booking.id,
            "slot_id": booking.slot_id,
            "client_name": booking.client_name,
            "client_email": booking.client_email,
            "status": booking.status,
            "starts_at": slot.starts_at,
            "ends_at": slot.ends_at,
            "created_at": booking.created_at,
            "cancelled_at": booking.cancelled_at,
        }
    )


def authorize(booking: Booking | None, token: str | None) -> Booking:
    if booking is None or not valid_token(token, booking.manage_token_hash):
        raise DomainError(404, "not_found", "Not Found")
    return booking


class BookingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: BookingCreate) -> BookingCreated:
        try:
            async with self.session.begin():
                slot = await repository.get_slot(self.session, data.slot_id, lock=True)
                if slot is None:
                    raise DomainError(404, "not_found", "Not Found")
                now = await repository.database_time(self.session)
                if slot.state != "open" or slot.starts_at <= now:
                    raise unavailable()
                if await repository.has_confirmed_booking(self.session, slot.id):
                    raise unavailable()
                token = new_manage_token()
                booking = Booking(
                    slot_id=slot.id,
                    client_name=data.client_name,
                    client_email=str(data.client_email),
                    status="confirmed",
                    manage_token_hash=token_hash(token),
                )
                self.session.add(booking)
                await self.session.flush()
                result = BookingCreated(**details(booking, slot).model_dump(), manage_token=token)
            # Never expose a token or success before the transaction commits.
            return result
        except IntegrityError as exc:
            # begin() has already rolled back. Do not mislabel other integrity failures.
            diag = getattr(exc.orig, "diag", None)
            if (
                getattr(exc.orig, "sqlstate", None) == "23505"
                and getattr(diag, "constraint_name", None) == "one_confirmed_booking_per_slot"
            ):
                raise unavailable() from None
            raise

    async def get(self, booking_id: UUID, token: str | None) -> BookingDetails:
        async with self.session.begin():
            booking = authorize(await repository.get_booking(self.session, booking_id), token)
            slot = await repository.get_slot(self.session, booking.slot_id)
            assert slot is not None  # FK and RESTRICT protect this relation.
            return details(booking, slot)

    async def cancel(self, booking_id: UUID, token: str | None) -> BookingDetails:
        async with self.session.begin():
            # Lookup/authorization is inside the transaction, before taking any row locks.
            booking = authorize(await repository.get_booking(self.session, booking_id), token)
            slot = await repository.get_slot(self.session, booking.slot_id, lock=True)
            assert slot is not None
            # Always lock slot -> booking and refresh the ORM identity after waiting.
            booking = authorize(
                await repository.get_booking(self.session, booking_id, lock=True), token
            )
            if booking.status != "cancelled":
                now = await repository.database_time(self.session)
                if slot.starts_at <= now:
                    raise DomainError(
                        409, "booking_started", "Встреча уже началась; отмена недоступна."
                    )
                booking.status = "cancelled"
                booking.cancelled_at = now
                await self.session.flush()
            result = details(booking, slot)
        return result
