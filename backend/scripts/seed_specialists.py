"""Idempotent synthetic catalog. Accounts have no usable password."""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.catalog.data import PEOPLE
from app.catalog.schedule import (
    LOCK_ID,
    extend_due,
    initialize_schedule,
    populate_slots,
    today_in_omsk,
)
from app.core.config import Settings
from app.models import Specialist, SpecialistService, User


def seed_specialists(url: str) -> dict[str, int]:
    engine = create_engine(url)
    result = {
        "specialists_created": 0,
        "specialists_skipped": 0,
        "slots_created": 0,
        "slots_skipped": 0,
    }
    try:
        with Session(engine) as db, db.begin():
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LOCK_ID})
            today = today_in_omsk(db)
            for index, (
                slug,
                name,
                category,
                specialty,
                summary,
                _weekdays,
                _start_hour,
                _end_hour,
            ) in enumerate(PEOPLE):
                user_id = uuid5(NAMESPACE_URL, "slotbook/catalog/user/" + slug)
                profile_id = uuid5(NAMESPACE_URL, "slotbook/catalog/specialist/" + slug)
                profile = db.get(Specialist, profile_id)
                if profile is None:
                    db.add(
                        User(
                            id=user_id,
                            role="specialist",
                            full_name=name,
                            timezone="Asia/Omsk",
                            normalized_email=slug + "@catalog.example.invalid",
                            password_hash="!disabled-synthetic",
                        )
                    )
                    db.flush()
                    visit = category in {"plumbing", "delivery"}
                    profile = Specialist(
                        id=profile_id,
                        user_id=user_id,
                        slug=slug,
                        display_name=name,
                        category_code=category,
                        specialization=specialty,
                        short_description=summary,
                        description=summary
                        + (
                            (
                                " Выезд по городу после согласования задачи и адреса. "
                                "Интервал обозначает окно начала выезда, а не длительность работы."
                            )
                            if visit
                            else (
                                " На консультации уточняем запрос и обсуждаем дальнейшие шаги. "
                                "Можно заранее подготовить вопросы и документы."
                            )
                        )
                        + " Вымышленный профиль для наполнения каталога.",
                        experience_years=5 + index,
                        city="Омск",
                        work_formats="visit"
                        if visit
                        else "office,online"
                        if category == "law"
                        else "office",
                        workplace="Учебный центр, кабинет " + str(101 + index) if not visit else "",
                        service_area="Омск, в пределах города" if visit else "",
                        timezone="Asia/Omsk",
                        publication_status="published",
                        services=[SpecialistService(name=specialty, description=summary)],
                    )
                    db.add(profile)
                    db.flush()
                    result["specialists_created"] += 1
                else:
                    result["specialists_skipped"] += 1
            state = initialize_schedule(
                db,
                today,
                today + timedelta(days=1) if result["specialists_created"] == 10 else None,
            )
            if state is not None:
                counts = populate_slots(db, state.initial_starts_on, state.generated_through, today)
                extension = extend_due(db, state, today)
                result["slots_created"] = counts[0] + extension["slots_created"]
                result["slots_skipped"] = counts[1] + extension["slots_skipped"]

        return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(seed_specialists(Settings().database_url))
