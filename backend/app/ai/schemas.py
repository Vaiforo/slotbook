from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.specialists.schemas import PublicSlot


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=500)


class Preference(BaseModel):
    """The model can describe a window, never a slot, tool or booking."""

    model_config = ConfigDict(extra="forbid", strict=True)
    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] | None
    time_from: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")] | None
    time_to: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")] | None
    needs_clarification: bool
    reason: Literal["date", "time", "unsupported"] | None


class SearchResult(BaseModel):
    status: Literal["found", "empty", "clarification", "unavailable"]
    message: str
    timezone: str
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    items: list[PublicSlot]
