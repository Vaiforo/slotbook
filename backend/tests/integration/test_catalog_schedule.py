from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session

import app.catalog.scheduler as scheduler
import scripts.seed_specialists as seed
from app.catalog.schedule import SCHEDULE_NAME, first_extension
from app.models import CatalogSchedule, Slot, Specialist


def test_weekly_extension_retries_parallel_workers_and_downtime(database, monkeypatch):
    clock = [date(2026, 11, 9)]
    monkeypatch.setattr(seed, "today_in_omsk", lambda db: clock[0])
    monkeypatch.setattr(scheduler, "today_in_omsk", lambda db: clock[0])
    engine = create_engine(database)
    try:
        assert scheduler.run_once(engine)["weeks_extended"] == 0  # no automatic seed
        assert seed.seed_specialists(database)["slots_created"] == 568
        with Session(engine) as db:
            state = db.get(CatalogSchedule, SCHEDULE_NAME)
            assert state.generated_through == date(2026, 11, 23)
            assert state.next_extension_on == date(2026, 11, 18)
        for day in [date(2026, 11, 11), date(2026, 11, 17)]:
            clock[0] = day
            assert scheduler.run_once(engine)["weeks_extended"] == 0
        clock[0] = date(2026, 11, 18)
        result = scheduler.run_once(engine)
        assert result["weeks_extended"] == 1
        assert result["slots_created"] == 284
        assert scheduler.run_once(engine)["weeks_extended"] == 0
        assert seed.seed_specialists(database)["slots_created"] == 0
        with engine.begin() as db:
            closed_id = db.scalar(select(Slot.id).order_by(Slot.starts_at.desc()).limit(1))
            db.execute(update(Slot).where(Slot.id == closed_id).values(state="closed"))
            profile_id = uuid5(NAMESPACE_URL, "slotbook/catalog/specialist/anna-belova")
            db.execute(
                update(Specialist)
                .where(Specialist.id == profile_id)
                .values(description="Owner edit")
            )
        clock[0] = date(2026, 11, 25)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: scheduler.run_once(engine), range(2)))
        assert sum(r["weeks_extended"] for r in results) == 1
        assert sum(r["slots_created"] for r in results) == 284
        with Session(engine) as db:
            assert db.get(Slot, closed_id).state == "closed"
            assert db.get(Specialist, profile_id).description == "Owner edit"
            state = db.get(CatalogSchedule, SCHEDULE_NAME)
            assert state.generated_through == date(2026, 12, 7)
            assert state.next_extension_on == date(2026, 12, 2)
            before = set(db.scalars(select(Slot.id)))
        clock[0] = date(2026, 12, 17)
        assert scheduler.run_once(engine)["weeks_extended"] == 3
        with Session(engine) as db:
            state = db.get(CatalogSchedule, SCHEDULE_NAME)
            assert state.generated_through == date(2026, 12, 28)
            assert state.next_extension_on == date(2026, 12, 23)
            new_slots = db.scalars(select(Slot).where(Slot.id.not_in(before))).all()
            assert new_slots
            assert all(slot.starts_at.date() > clock[0] for slot in new_slots)
        # Roll back both the appended slots and the new horizon after a failure.
        clock[0] = date(2026, 12, 23)
        with Session(engine) as db:
            count = db.scalar(select(func.count()).select_from(Slot))
        original = scheduler.extend_due

        def failing_extension(*args):
            original(*args)
            raise RuntimeError("Failure after flush")

        with monkeypatch.context() as patch:
            patch.setattr(scheduler, "extend_due", failing_extension)
            with pytest.raises(RuntimeError):
                scheduler.run_once(engine)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Slot)) == count
            assert db.get(CatalogSchedule, SCHEDULE_NAME).next_extension_on == clock[0]
        assert scheduler.run_once(engine)["weeks_extended"] == 1
        # Adoption after an upgrade does not recreate profiles or reset their edits.
        with Session(engine) as db, db.begin():
            db.delete(db.get(CatalogSchedule, SCHEDULE_NAME))
        assert scheduler.run_once(engine)["weeks_extended"] >= 0
        assert seed.seed_specialists(database)["specialists_created"] == 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("weekday", range(7))
def test_first_extension_is_in_second_seven_day_period(weekday):
    start = date(2026, 11, 9) + timedelta(days=weekday)
    first = first_extension(start)
    assert first.weekday() == 2
    assert 7 <= (first - start).days <= 13
