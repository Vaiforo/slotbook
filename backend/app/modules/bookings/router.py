from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import DomainError, ErrorResponse
from app.modules.auth.dependencies import ClientUser
from app.modules.bookings.schemas import (
    AccountBookingCreate,
    BookingCreate,
    BookingCreated,
    BookingDetails,
)
from app.modules.bookings.service import BookingService

router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["bookings"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 409, 413)},
)
Session = Annotated[AsyncSession, Depends(get_session)]
bearer = HTTPBearer(
    auto_error=False,
    scheme_name="ManageToken",
    description="Secret token returned by booking creation; no cookie or query-string fallback.",
)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@router.post(
    "",
    status_code=201,
    response_model=BookingCreated,
    operation_id="create_booking",
    responses={code: {"model": ErrorResponse} for code in (429, 503)},
)
async def create_booking(data: AccountBookingCreate, client: ClientUser) -> BookingCreated:
    if not client.user.full_name:
        raise DomainError(409, "profile_incomplete", "Please complete your account name")
    try:
        snapshot = BookingCreate(
            slot_id=data.slot_id,
            client_name=client.user.full_name,
            client_email=client.user.normalized_email,
        )
    except ValueError:
        raise DomainError(
            409, "profile_incomplete", "Please update your account contacts"
        ) from None
    return await BookingService(client.db).create(snapshot, client_user_id=client.user.id)


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
