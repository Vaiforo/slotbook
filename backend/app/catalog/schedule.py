"""Durable, idempotent weekly extension for synthetic specialists only."""

from datetime import date, datetime, time, timedelta
from typing import cast
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.catalog.data import PEOPLE
from app.models import CatalogSchedule, Slot, Specialist, User

LOCK_ID = 8273902
SCHEDULE_NAME = "synthetic-specialists"
ZONE = ZoneInfo("Asia/Omsk")


def today_in_omsk(db: Session) -> date:
    return cast(datetime, db.scalar(select(func.clock_timestamp()))).astimezone(ZONE).date()


def first_extension(initial_starts_on: date) -> date:
    after_first_week = initial_starts_on + timedelta(days=7)
    return after_first_week + timedelta(days=(2 - after_first_week.weekday()) % 7)


def initialize_schedule(
    db: Session, today: date, initial_starts_on: date | None = None
) -> CatalogSchedule | None:
    """Adopt existing seeded accounts without recreating or editing them."""
    state = db.get(CatalogSchedule, SCHEDULE_NAME)
    if state is not None:
        return state
    ids = [uuid5(NAMESPACE_URL, "slotbook/catalog/user/" + person[0]) for person in PEOPLE]
    created_at = db.scalar(select(func.min(User.created_at)).where(User.id.in_(ids)))
    if created_at is None:
        return None
    start = initial_starts_on or (
        min(created_at.astimezone(ZONE).date(), today) + timedelta(days=1)
    )
    state = CatalogSchedule(
        name=SCHEDULE_NAME,
        initial_starts_on=start,
        generated_through=start + timedelta(days=13),
        next_extension_on=first_extension(start),
    )
    db.add(state)
    db.flush()
    return state


def populate_slots(db: Session, start: date, end: date, today: date) -> tuple[int, int]:
    created = skipped = 0
    for slug, _, _, _, _, weekdays, start_hour, end_hour in PEOPLE:
        profile_id = uuid5(NAMESPACE_URL, "slotbook/catalog/specialist/" + slug)
        profile = db.scalar(select(Specialist).where(Specialist.id == profile_id).with_for_update())
        if profile is None or profile.timezone != "Asia/Omsk":
            continue
        day = max(start, today + timedelta(days=1))
        while day <= end:
            if day.weekday() in weekdays:
                begins = datetime.combine(day, time(start_hour), ZONE)
                for minute in range(0, (end_hour - start_hour) * 60, 30):
                    instant = begins + timedelta(minutes=minute)
                    value = db.scalar(
                        insert(Slot)
                        .values(
                            id=uuid5(profile_id, instant.isoformat()),
                            specialist_id=profile_id,
                            starts_at=instant,
                            ends_at=instant + timedelta(minutes=30),
                        )
                        .on_conflict_do_nothing()
                        .returning(Slot.id)
                    )
                    if value is None:
                        skipped += 1
                    else:
                        created += 1
            day += timedelta(days=1)
    return created, skipped


def extend_due(db: Session, state: CatalogSchedule, today: date) -> dict[str, int]:
    if today < state.next_extension_on:
        return {"weeks_extended": 0, "slots_created": 0, "slots_skipped": 0}
    weeks = (today - state.next_extension_on).days // 7 + 1
    start = state.generated_through + timedelta(days=1)
    end = state.generated_through + timedelta(days=7 * weeks)
    created, skipped = populate_slots(db, start, end, today)
    state.generated_through = end
    state.next_extension_on += timedelta(days=7 * weeks)
    db.flush()
    return {"weeks_extended": weeks, "slots_created": created, "slots_skipped": skipped}
