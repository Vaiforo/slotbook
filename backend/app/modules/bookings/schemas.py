from typing import Annotated, Literal
from unicodedata import category
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: UUID
    client_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    client_email: Annotated[EmailStr, Field(max_length=320)]

    @field_validator("client_name")
    @classmethod
    def no_control_characters(cls, value: str) -> str:
        if any(category(char) == "Cc" for char in value):
            raise ValueError("Control characters are not allowed")
        return value


class BookingDetails(BaseModel):
    id: UUID
    slot_id: UUID
    client_name: str
    client_email: str
    status: Literal["confirmed", "cancelled"]
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    created_at: AwareDatetime
    cancelled_at: AwareDatetime | None


class BookingCreated(BookingDetails):
    manage_token: str = Field(
        description=(
            "Returned once after commit; send as Authorization: Bearer for management. "
            "Never put it in a URL query."
        )
    )
