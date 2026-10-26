from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.specialists.repository import available_slots, find_specialist
from app.modules.specialists.schemas import PublicSlot, PublicSpecialist, SlotFilters, SlotPage

router = APIRouter(prefix="/api/v1/specialists", tags=["specialists"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{slug}", response_model=PublicSpecialist, operation_id="get_specialist")
async def get_specialist(slug: str, session: Session) -> PublicSpecialist:
    specialist = await find_specialist(session, slug)
    if specialist is None:
        raise HTTPException(404)
    return PublicSpecialist.model_validate(specialist)


@router.get("/{slug}/slots", response_model=SlotPage, operation_id="get_available_slots")
async def get_available_slots(
    slug: str, filters: Annotated[SlotFilters, Query()], session: Session
) -> SlotPage:
    specialist = await find_specialist(session, slug)
    if specialist is None:
        raise HTTPException(404)
    slots = await available_slots(session, specialist, filters)
    return SlotPage(
        items=[PublicSlot.model_validate(slot) for slot in slots],
        limit=filters.limit,
        offset=filters.offset,
    )
