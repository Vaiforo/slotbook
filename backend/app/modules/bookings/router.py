from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ErrorResponse
from app.modules.bookings.schemas import BookingCreate, BookingCreated, BookingDetails
from app.modules.bookings.service import BookingService

router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["bookings"],
    responses={409: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
Session = Annotated[AsyncSession, Depends(get_session)]
bearer = HTTPBearer(
    auto_error=False,
    scheme_name="ManageToken",
    description="Secret token returned by booking creation; no cookie or query-string fallback.",
)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@router.post("", status_code=201, response_model=BookingCreated, operation_id="create_booking")
async def create_booking(data: BookingCreate, session: Session) -> BookingCreated:
    return await BookingService(session).create(data)


@router.get("/{booking_id}", response_model=BookingDetails, operation_id="get_booking")
async def get_booking(
    booking_id: UUID, session: Session, credentials: Credentials
) -> BookingDetails:
    return await BookingService(session).get(
        booking_id, credentials.credentials if credentials else None
    )


@router.post("/{booking_id}/cancel", response_model=BookingDetails, operation_id="cancel_booking")
async def cancel_booking(
    booking_id: UUID, session: Session, credentials: Credentials
) -> BookingDetails:
    return await BookingService(session).cancel(
        booking_id, credentials.credentials if credentials else None
    )
