"""Explicit, repeatable synthetic data. Password activation is explicit and opt-in."""

from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, delete, text
from sqlalchemy.dialects.postgresql import insert

from app.models import Session, Slot, Specialist, User
from app.modules.owner.security import hasher

FIXTURE_USER = uuid5(NAMESPACE_URL, "slotbook/test-fixture/user")
FIXTURE_SPECIALIST = uuid5(NAMESPACE_URL, "slotbook/test-fixture/specialist")


def seed_test_fixture(url: str, password: str | None = None) -> None:
    if password is not None and len(password) < 12:
        raise ValueError("Demo password must contain at least 12 characters")
    if not any(name in url for name in ("slotbook_test_", "slotbook_browser_")):
        raise ValueError("Fixtures require a disposable test database")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(8273901)"))
            conn.execute(
                insert(User)
                .values(
                    id=FIXTURE_USER,
                    role="specialist",
                    normalized_email="fixture@example.invalid",
                    password_hash="!disabled-test-owner",
                )
                .on_conflict_do_nothing(index_elements=[User.id])
            )
            if password is not None:
                conn.execute(delete(Session).where(Session.user_id == FIXTURE_USER))
                conn.execute(
                    User.__table__.update()
                    .where(User.id == FIXTURE_USER)
                    .values(password_hash=hasher.hash(password))
                )
            conn.execute(
                insert(Specialist)
                .values(
                    id=FIXTURE_SPECIALIST,
                    publication_status="published",
                    user_id=FIXTURE_USER,
                    slug="fixture",
                    display_name="Тестовый специалист",
                    timezone="Asia/Omsk",
                )
                .on_conflict_do_nothing(index_elements=[Specialist.id])
            )
            now = conn.scalar(text("SELECT CURRENT_TIMESTAMP"))
            tomorrow = now.astimezone(ZoneInfo("Asia/Omsk")).date() + timedelta(days=1)
            start = datetime.combine(tomorrow, time(10), ZoneInfo("Asia/Omsk"))
            for offset in range(4):
                begins = start + timedelta(minutes=30 * offset)
                conn.execute(
                    insert(Slot)
                    .values(
                        id=uuid5(FIXTURE_SPECIALIST, begins.isoformat()),
                        specialist_id=FIXTURE_SPECIALIST,
                        starts_at=begins,
                        ends_at=begins + timedelta(minutes=30),
                    )
                    .on_conflict_do_nothing()
                )
    finally:
        engine.dispose()
