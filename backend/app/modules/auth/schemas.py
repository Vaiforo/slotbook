from typing import Literal, Self
from unicodedata import category
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.specialists.schemas import PublicSpecialist


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=30)
    timezone: str = Field(max_length=100)

    @field_validator("full_name")
    @classmethod
    def printable_name(cls, value: str) -> str:
        if any(category(char) == "Cc" for char in value):
            raise ValueError("Control characters are not allowed")
        return value

    @field_validator("full_name", "phone", "timezone", mode="before")
    @classmethod
    def trim(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("Unknown IANA timezone") from None
        return value


class Register(ProfileUpdate):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    role: Literal["client", "specialist"]
    category_code: Literal["medicine", "plumbing", "law", "delivery"] | None = None

    @model_validator(mode="after")
    def category_matches_role(self) -> Self:
        if (self.role == "specialist") != (self.category_code is not None):
            raise ValueError("Category is required only for specialists")
        return self


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class Identity(BaseModel):
    id: UUID
    email: str
    role: Literal["client", "specialist"]
    full_name: str
    phone: str
    timezone: str
    csrf_token: str
    specialist: PublicSpecialist | None
