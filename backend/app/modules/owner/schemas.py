from datetime import UTC, timedelta
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.modules.bookings.schemas import BookingDetails
from app.modules.specialists.schemas import SlotFilters


class SlotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def duration(self) -> Self:
        if self.ends_at.astimezone(UTC) - self.starts_at.astimezone(UTC) != timedelta(minutes=30):
            raise ValueError("Slots must last exactly 30 minutes")
        return self


class SlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["open", "closed"]


class OwnerSlot(SlotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    state: Literal["open", "closed"]


class BookingFilters(SlotFilters):
    status: Literal["confirmed", "cancelled"] | None = None


class OwnerBookings(BaseModel):
    items: list[BookingDetails]
    limit: int
    offset: int


class ScheduleSlot(OwnerSlot):
    has_booking: bool


class OwnerSlots(BaseModel):
    items: list[ScheduleSlot]
    limit: int
    offset: int
