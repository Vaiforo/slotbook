"""Explicit, repeatable synthetic data. Never creates a usable login password."""

from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.models import Slot, Specialist, User

DEMO_USER = uuid5(NAMESPACE_URL, "slotbook/demo/user")
DEMO_SPECIALIST = uuid5(NAMESPACE_URL, "slotbook/demo/specialist")


def seed_demo(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(8273901)"))
            conn.execute(
                insert(User)
                .values(
                    id=DEMO_USER,
                    normalized_email="demo@example.invalid",
                    password_hash="!disabled-demo-owner",
                )
                .on_conflict_do_nothing(index_elements=[User.id])
            )
            conn.execute(
                insert(Specialist)
                .values(
                    id=DEMO_SPECIALIST,
                    user_id=DEMO_USER,
                    slug="demo",
                    display_name="Демо-специалист",
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
                        id=uuid5(DEMO_SPECIALIST, begins.isoformat()),
                        specialist_id=DEMO_SPECIALIST,
                        starts_at=begins,
                        ends_at=begins + timedelta(minutes=30),
                    )
                    .on_conflict_do_nothing()
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed_demo(Settings().database_url)
    print("Demo data ready (demo@example.invalid; login disabled).")
