from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError, ErrorResponse
from app.models import Slot, Specialist, SpecialistService
from app.modules.auth.dependencies import SpecialistUser
from app.modules.bookings.repository import database_time
from app.modules.specialists.account_schemas import (
    BatchResult,
    ProfessionalDetails,
    ProfessionalSave,
    ServicesUpdate,
    ShiftBatch,
)

router = APIRouter(
    prefix="/api/v1/me/specialist",
    tags=["professional-account"],
    responses={c: {"model": ErrorResponse} for c in (401, 403, 409)},
)


async def own_profile(owner: SpecialistUser) -> Specialist:
    profile = await owner.db.scalar(
        select(Specialist)
        .where(Specialist.user_id == owner.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise DomainError(404, "not_found", "Profile not found")
    return profile


def publication_errors(profile: Specialist) -> list[str]:
    missing = [
        name
        for name in (
            "display_name",
            "category_code",
            "specialization",
            "short_description",
            "description",
            "city",
            "work_formats",
            "timezone",
        )
        if not getattr(profile, name)
    ]
    if "office" in profile.work_formats.split(",") and not profile.workplace:
        missing.append("workplace")
    if "visit" in profile.work_formats.split(",") and not profile.service_area:
        missing.append("service_area")
    return missing


@router.get("", response_model=ProfessionalDetails)
async def get_profile(owner: SpecialistUser) -> Specialist:
    return await own_profile(owner)


@router.patch("", response_model=ProfessionalDetails)
async def edit_profile(data: ProfessionalSave, owner: SpecialistUser) -> Specialist:
    profile = await own_profile(owner)
    if data.timezone != profile.timezone and await owner.db.scalar(
        select(Slot.id)
        .where(Slot.specialist_id == profile.id, Slot.starts_at > await database_time(owner.db))
        .limit(1)
    ):
        raise DomainError(409, "timezone_has_slots", "Cannot change timezone with future slots")
    for name, value in data.model_dump(exclude={"services"}).items():
        setattr(profile, name, value)
    if data.services is not None:
        profile.services = [SpecialistService(**service.model_dump()) for service in data.services]
    if profile.publication_status == "published" and publication_errors(profile):
        raise DomainError(409, "profile_incomplete", "Unpublish before removing required fields")
    await owner.db.flush()
    return profile


@router.put("/services", response_model=ProfessionalDetails)
async def edit_services(data: ServicesUpdate, owner: SpecialistUser) -> Specialist:
    profile = await own_profile(owner)
    profile.services = [SpecialistService(**service.model_dump()) for service in data.services]
    await owner.db.flush()
    return profile


@router.post("/publish", response_model=ProfessionalDetails)
async def publish(owner: SpecialistUser) -> Specialist:
    profile = await own_profile(owner)
    missing = publication_errors(profile)
    if missing:
        raise DomainError(409, "profile_incomplete", "Required fields: " + ", ".join(missing))
    profile.publication_status = "published"
    await owner.db.flush()
    return profile


@router.post("/unpublish", response_model=ProfessionalDetails)
async def unpublish(owner: SpecialistUser) -> Specialist:
    profile = await own_profile(owner)
    profile.publication_status = "draft"
    await owner.db.flush()
    return profile


def generate_slots(data: ShiftBatch, timezone: str) -> list[tuple[datetime, datetime]]:
    zone = ZoneInfo(timezone)
    result = []
    day = data.date_from
    while day <= data.date_to:
        if day.weekday() in data.weekdays:
            cursor = datetime.combine(day, data.start)
            end = datetime.combine(day, data.end)
            while cursor < end:
                stop = cursor + timedelta(minutes=30)
                if not any(cursor.time() < b.end and stop.time() > b.start for b in data.breaks):
                    instants = []
                    for local in (cursor, stop):
                        first = local.replace(tzinfo=zone, fold=0)
                        second = local.replace(tzinfo=zone, fold=1)
                        if (
                            first.utcoffset() != second.utcoffset()
                            or first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local
                        ):
                            raise DomainError(
                                422,
                                "ambiguous_time",
                                "Selected time does not exist or is ambiguous",
                            )
                        instants.append(first.astimezone(UTC))
                    result.append((instants[0], instants[1]))
                cursor = stop
        day += timedelta(days=1)
    if not result or len(result) > 1000:
        raise DomainError(422, "batch_size", "Select 1 to 1000 slots")
    return result


@router.post("/slots/preview", response_model=BatchResult)
async def preview(data: ShiftBatch, owner: SpecialistUser) -> BatchResult:
    profile = await own_profile(owner)
    return BatchResult(count=len(await checked_slots(data, profile, owner)))


async def checked_slots(
    data: ShiftBatch, profile: Specialist, owner: SpecialistUser
) -> list[tuple[datetime, datetime]]:
    slots = generate_slots(data, profile.timezone)
    now = await database_time(owner.db)
    if any(start <= now for start, _ in slots):
        raise DomainError(409, "slot_started", "All slots must be in the future")
    existing = (
        await owner.db.scalars(
            select(Slot).where(
                Slot.specialist_id == profile.id,
                Slot.starts_at < slots[-1][1],
                Slot.ends_at > slots[0][0],
            )
        )
    ).all()
    conflicts = [
        start.isoformat()
        for start, end in slots
        if any(start < s.ends_at and end > s.starts_at for s in existing)
    ]
    if conflicts:
        raise DomainError(409, "slot_overlap", "Conflicting intervals: " + ", ".join(conflicts))
    return slots


@router.post("/slots/batch", status_code=201, response_model=BatchResult)
async def create_batch(data: ShiftBatch, owner: SpecialistUser) -> BatchResult:
    profile = await own_profile(owner)
    slots = await checked_slots(data, profile, owner)
    try:
        async with owner.db.begin_nested():
            owner.db.add_all(
                [
                    Slot(specialist_id=profile.id, starts_at=start, ends_at=end)
                    for start, end in slots
                ]
            )
            await owner.db.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23P01":
            raise DomainError(409, "slot_overlap", "Schedule changed; preview again") from None
        raise
    return BatchResult(count=len(slots))
