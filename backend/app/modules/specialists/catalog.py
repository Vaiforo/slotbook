from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Booking, Slot, Specialist, SpecialistCategory, User
from app.modules.specialists.schemas import PublicSpecialist

router = APIRouter(prefix="/api/v1", tags=["catalog"])


class CatalogFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    q: str = Field(default="", max_length=100)
    category: str = Field(default="", max_length=30)
    city: str = Field(default="", max_length=100)
    available: bool = False
    limit: int = Field(default=12, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


class CatalogItem(PublicSpecialist):
    next_available_at: datetime | None


class CatalogPage(BaseModel):
    items: list[CatalogItem]
    total: int
    limit: int
    offset: int


class Category(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str


@router.get("/specialist-categories", response_model=list[Category])
async def categories(
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Sequence[SpecialistCategory]:
    return (
        await db.scalars(select(SpecialistCategory).order_by(SpecialistCategory.sort_order))
    ).all()


@router.get("/specialists", response_model=CatalogPage)
async def catalog(
    filters: Annotated[CatalogFilters, Query()], db: Annotated[AsyncSession, Depends(get_session)]
) -> CatalogPage:
    booked = (
        select(Booking.id).where(Booking.slot_id == Slot.id, Booking.status == "confirmed").exists()
    )
    nearest = (
        select(func.min(Slot.starts_at))
        .where(
            Slot.specialist_id == Specialist.id,
            Slot.state == "open",
            Slot.starts_at > func.now(),
            ~booked,
        )
        .correlate(Specialist)
        .scalar_subquery()
    )
    conditions = [Specialist.publication_status == "published", User.is_active.is_(True)]
    if filters.category:
        conditions.append(Specialist.category_code == filters.category)
    if filters.city:
        conditions.append(func.lower(Specialist.city) == filters.city.lower())
    if filters.q:
        term = "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(
            Specialist.display_name.ilike(term)
            | Specialist.specialization.ilike(term)
            | Specialist.short_description.ilike(term)
        )
    if filters.available:
        conditions.append(nearest.is_not(None))
    total = await db.scalar(
        select(func.count()).select_from(Specialist).join(User).where(*conditions)
    )
    rows = await db.execute(
        select(Specialist, nearest.label("next_available_at"))
        .join(User)
        .where(*conditions)
        .order_by(nearest.asc().nulls_last(), Specialist.display_name, Specialist.id)
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return CatalogPage(
        items=[
            CatalogItem(**PublicSpecialist.model_validate(s).model_dump(), next_available_at=t)
            for s, t in rows
        ],
        total=total or 0,
        limit=filters.limit,
        offset=filters.offset,
    )
