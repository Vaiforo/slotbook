"""Idempotent synthetic catalog. Accounts have no usable password."""

from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Slot, Specialist, SpecialistService, User

# slug, name, category, specialty, short description, weekdays, working hours
PEOPLE = [
    (
        "anna-belova",
        "Анна Белова",
        "medicine",
        "Терапевт",
        "Первичный приём и профилактические консультации.",
        [0, 2, 4],
        9,
        13,
    ),
    (
        "mikhail-sokolov",
        "Михаил Соколов",
        "medicine",
        "Невролог",
        "Первичные и повторные консультации по неврологии.",
        [1, 3],
        14,
        18,
    ),
    (
        "elena-morozova",
        "Елена Морозова",
        "medicine",
        "Дерматолог",
        "Консультации по состоянию кожи и повседневному уходу.",
        [0, 3, 5],
        10,
        14,
    ),
    (
        "sergey-volkov",
        "Сергей Волков",
        "plumbing",
        "Бытовая сантехника",
        "Замена смесителей, сифонов и устранение протечек.",
        [0, 1, 2, 3, 4],
        9,
        12,
    ),
    (
        "dmitry-orlov",
        "Дмитрий Орлов",
        "plumbing",
        "Подключение бытовой техники",
        "Подключение стиральных и посудомоечных машин.",
        [1, 2, 3, 4, 5],
        13,
        17,
    ),
    (
        "pavel-kuznetsov",
        "Павел Кузнецов",
        "plumbing",
        "Водоснабжение и отопление",
        "Диагностика домашних систем водоснабжения и отопления.",
        [0, 2, 4],
        14,
        18,
    ),
    (
        "olga-lebedeva",
        "Ольга Лебедева",
        "law",
        "Договоры и права потребителей",
        "Разбор договоров, претензий и потребительских споров.",
        [0, 1, 2, 3],
        10,
        13,
    ),
    (
        "andrey-mironov",
        "Андрей Миронов",
        "law",
        "Трудовое право",
        "Консультации по трудовым отношениям и подготовке документов.",
        [1, 2, 3, 4],
        15,
        19,
    ),
    (
        "irina-alekseeva",
        "Ирина Алексеева",
        "delivery",
        "Документы и небольшие посылки",
        "Доставка документов и небольших отправлений по Омску.",
        [0, 1, 2, 3, 4],
        9,
        12,
    ),
    (
        "artem-nikitin",
        "Артём Никитин",
        "delivery",
        "Заказы и покупки",
        "Забор интернет-заказов и доставка небольших покупок.",
        [1, 2, 3, 4, 5],
        16,
        20,
    ),
]


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
            db.execute(text("SELECT pg_advisory_xact_lock(8273902)"))
            zone = ZoneInfo("Asia/Omsk")
            today = db.scalar(select(text("CURRENT_TIMESTAMP"))).astimezone(zone).date()
            for index, (
                slug,
                name,
                category,
                specialty,
                summary,
                weekdays,
                start_hour,
                end_hour,
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
                # Respect owner changes to the timezone rather than extending in the wrong zone.
                if profile.timezone != "Asia/Omsk":
                    continue
                for offset in range(1, 15):
                    day = today + timedelta(days=offset)
                    if day.weekday() not in weekdays:
                        continue
                    start = datetime.combine(day, time(start_hour), zone)
                    for minute in range(0, (end_hour - start_hour) * 60, 30):
                        begins = start + timedelta(minutes=minute)
                        statement = (
                            insert(Slot)
                            .values(
                                id=uuid5(profile_id, begins.isoformat()),
                                specialist_id=profile_id,
                                starts_at=begins,
                                ends_at=begins + timedelta(minutes=30),
                            )
                            .on_conflict_do_nothing()
                            .returning(Slot.id)
                        )
                        created = db.scalar(statement)
                        result["slots_created" if created else "slots_skipped"] += 1
        return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(seed_specialists(Settings().database_url))
