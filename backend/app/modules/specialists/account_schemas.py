from datetime import date, time
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.auth.schemas import ProfileUpdate


class ServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class ProfessionalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=200)
    category_code: Literal["medicine", "plumbing", "law", "delivery"] | None = None
    specialization: str = Field(default="", max_length=200)
    short_description: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=10000)
    experience_years: int | None = Field(default=None, ge=0, le=80)
    city: str = Field(default="", max_length=100)
    work_formats: str = Field(default="", max_length=100)
    workplace: str = Field(default="", max_length=500)
    service_area: str = Field(default="", max_length=500)
    timezone: str

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        ProfileUpdate(full_name=self.display_name, timezone=self.timezone)
        formats = self.work_formats.split(",") if self.work_formats else []
        if len(formats) != len(set(formats)) or any(
            f not in {"office", "online", "visit"} for f in formats
        ):
            raise ValueError("Unknown work format")
        return self


class ProfessionalSave(ProfessionalProfile):
    services: list[ServiceInput] | None = Field(default=None, max_length=30)


class ProfessionalDetails(ProfessionalProfile):
    slug: str
    publication_status: Literal["draft", "published"]
    services: list[ServiceInput]


class ServicesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    services: list[ServiceInput] = Field(max_length=30)


class BreakPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: time
    end: time


class ShiftBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_from: date
    date_to: date
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start: time
    end: time
    breaks: list[BreakPeriod] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if not 0 <= (self.date_to - self.date_from).days < 90:
            raise ValueError("Select 1 to 90 days")
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            d not in range(7) for d in self.weekdays
        ):
            raise ValueError("Weekdays must be distinct values 0 to 6")
        periods = [(self.start, self.end)] + [(b.start, b.end) for b in self.breaks]
        for start, end in periods:
            if start >= end or any(
                t.tzinfo or t.second or t.microsecond or t.minute % 30 for t in (start, end)
            ):
                raise ValueError("Use same-day periods on a 30-minute grid")
        previous = self.start
        for pause in sorted(self.breaks, key=lambda b: b.start):
            if pause.start < previous or pause.end > self.end:
                raise ValueError("Breaks must not overlap and must be within working hours")
            previous = pause.end
        return self


class BatchResult(BaseModel):
    count: int
