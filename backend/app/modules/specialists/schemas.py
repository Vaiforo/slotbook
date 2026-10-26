from datetime import UTC, timedelta
from typing import Annotated, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class PublicSpecialist(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    slug: str
    display_name: str
    timezone: str


class PublicSlot(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class SlotFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_: Annotated[
        AwareDatetime,
        Field(
            alias="from",
            description="Inclusive start; ISO 8601 with UTC offset. Range at most 31 days.",
        ),
    ]
    to: AwareDatetime = Field(description="Exclusive start-time bound; ISO 8601 with UTC offset.")
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        delta = self.to.astimezone(UTC) - self.from_.astimezone(UTC)
        if not timedelta(0) < delta <= timedelta(days=31):
            raise ValueError("Range must be positive and at most 31 days")
        return self


class SlotPage(BaseModel):
    items: list[PublicSlot]
    limit: int
    offset: int
