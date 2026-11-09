from collections import Counter

from sqlalchemy import create_engine, func, select, update

from app.models import Booking, Slot, Specialist, User
from scripts.seed_specialists import seed_specialists


def test_legacy_demo_cleanup_preserves_unrelated_profiles(database):
    from datetime import UTC, datetime, timedelta
    from uuid import NAMESPACE_URL, uuid4, uuid5

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session

    from app.models import NotificationDelivery, OutboxEvent

    engine = create_engine(database)
    demo_user = uuid5(NAMESPACE_URL, "slotbook/demo/user")
    demo_profile = uuid5(NAMESPACE_URL, "slotbook/demo/specialist")
    unrelated = uuid4()
    try:
        with Session(engine) as db, db.begin():
            db.add_all(
                [
                    User(
                        id=demo_user,
                        normalized_email="old-demo@example.com",
                        password_hash="!disabled",
                    ),
                    User(
                        id=unrelated,
                        normalized_email="unrelated@example.com",
                        password_hash="!disabled",
                    ),
                ]
            )
            db.flush()
            db.add(
                Specialist(id=demo_profile, user_id=demo_user, slug="demo", display_name="Old demo")
            )
            db.flush()
            start = datetime.now(UTC) + timedelta(days=1)
            slot = Slot(
                specialist_id=demo_profile, starts_at=start, ends_at=start + timedelta(minutes=30)
            )
            db.add(slot)
            db.flush()
            booking = Booking(
                slot_id=slot.id,
                client_name="Old client",
                client_email="old@example.com",
                manage_token_hash="a" * 64,
            )
            db.add(booking)
            db.flush()
            event = OutboxEvent(booking_id=booking.id, kind="booking_created")
            db.add(event)
            db.flush()
            db.add(NotificationDelivery(event_id=event.id))
        command.downgrade(Config("alembic.ini"), "d1420a02")
        command.upgrade(Config("alembic.ini"), "head")
        with Session(engine) as db:
            assert db.get(User, demo_user) is None
            assert db.get(Specialist, demo_profile) is None
            assert db.get(User, unrelated) is not None
            assert db.scalar(select(func.count()).select_from(Booking)) == 0
    finally:
        engine.dispose()


def test_seed_exact_distribution_repeatability_and_owner_changes(database):
    first = seed_specialists(database)
    assert first["specialists_created"] == 10
    engine = create_engine(database)
    try:
        with engine.begin() as db:
            categories = db.execute(select(Specialist.category_code)).scalars().all()
            assert Counter(categories) == {"medicine": 3, "plumbing": 3, "law": 2, "delivery": 2}
            assert db.scalar(select(func.count()).select_from(Booking)) == 0
            assert all(
                p.startswith("!disabled") for p in db.execute(select(User.password_hash)).scalars()
            )
            profile_id = db.scalar(select(Specialist.id).limit(1))
            slot_id = db.scalar(select(Slot.id).limit(1))
            db.execute(
                update(Specialist)
                .where(Specialist.id == profile_id)
                .values(description="Owner edited")
            )
            db.execute(update(Slot).where(Slot.id == slot_id).values(state="closed"))
        repeated = seed_specialists(database)
        assert repeated["specialists_created"] == 0
        assert repeated["slots_created"] == 0
        with engine.connect() as db:
            assert (
                db.scalar(select(Specialist.description).where(Specialist.id == profile_id))
                == "Owner edited"
            )
            assert db.scalar(select(Slot.state).where(Slot.id == slot_id)) == "closed"
    finally:
        engine.dispose()
