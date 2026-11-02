import logging
from datetime import UTC, datetime, time, timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import Date, cast, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import LLMClient, LLMUnavailable
from app.ai.schemas import Preference, SearchResult
from app.models import AIUsage, Specialist
from app.modules.specialists.repository import available_slots
from app.modules.specialists.schemas import PublicSlot, SlotFilters

logger = logging.getLogger(__name__)
CLARIFY = {
    "date": "Укажите один день в ближайшие 30 дней, например: завтра после 15:00.",
    "time": "Уточните время в 24-часовом формате и день, например: завтра с 15:00 до 18:00.",
    "unsupported": (
        "Опишите один день и желаемое время консультации. Записаться можно после выбора слота."
    ),
}
UNAVAILABLE = "Поиск по описанию сейчас недоступен. Выберите день и время в календаре."


class Clarification(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def window(preference: Preference, now: datetime, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    if preference.needs_clarification:
        raise Clarification(preference.reason or "date")
    if preference.reason or preference.date is None:
        raise Clarification("date")
    try:
        day = datetime.strptime(preference.date, "%Y-%m-%d").date()
    except ValueError:
        raise Clarification("date") from None
    if not now.astimezone(zone).date() <= day <= now.astimezone(zone).date() + timedelta(days=30):
        raise Clarification("date")
    if (preference.time_from is None) != (preference.time_to is None):
        raise Clarification("time")
    start = datetime.combine(day, time.fromisoformat(preference.time_from or "00:00"), zone)
    end = (
        datetime.combine(day, time.fromisoformat(preference.time_to), zone)
        if preference.time_to
        else datetime.combine(day + timedelta(days=1), time(), zone)
    )
    # Reject ambiguous/nonexistent local times during DST instead of choosing a fold.
    for value in (start, end):
        if value.replace(fold=0).utcoffset() != value.replace(
            fold=1
        ).utcoffset() or value.astimezone(UTC).astimezone(zone).replace(
            tzinfo=None
        ) != value.replace(tzinfo=None):
            raise Clarification("time")
    if end <= start or end <= now.astimezone(zone):
        raise Clarification("time")
    return start, end


async def reserve_call(session: AsyncSession, limit: int) -> bool:
    """One durable global reservation per attempt, committed BEFORE external I/O."""
    day = cast(func.timezone("UTC", func.clock_timestamp()), Date)
    statement = insert(AIUsage).values(day=day, calls=1)
    reserved = await session.scalar(
        statement.on_conflict_do_update(
            index_elements=[AIUsage.day],
            set_={"calls": AIUsage.calls + 1},
            where=AIUsage.calls < limit,
        ).returning(AIUsage.calls)
    )
    await session.commit()
    return reserved is not None


async def search(
    session: AsyncSession, specialist: Specialist, text: str, client: LLMClient
) -> SearchResult:
    started = perf_counter()
    now = datetime.now(UTC).astimezone(ZoneInfo(specialist.timezone))
    status = "unavailable"
    try:
        raw = await client.extract(text, now, specialist.timezone)
        preference = Preference.model_validate_json(raw)
        start, end = window(preference, now, specialist.timezone)
        filters = SlotFilters.model_validate({"from": start, "to": end, "limit": 48})
        slots = await available_slots(session, specialist, filters)
        status = "found" if slots else "empty"
        return SearchResult(
            status=status,
            message=(
                "Выберите время, затем заполните форму для подтверждения записи."
                if slots
                else "Свободного времени нет. Попробуйте другой день или календарь."
            ),
            timezone=specialist.timezone,
            **{"from": start, "to": end},
            items=[PublicSlot.model_validate(slot) for slot in slots],
        )
    except Clarification as exc:
        status = "clarification"
        return SearchResult(
            status=status, message=CLARIFY[exc.reason], timezone=specialist.timezone, items=[]
        )
    except LLMUnavailable, ValidationError:
        return SearchResult(
            status="unavailable", message=UNAVAILABLE, timezone=specialist.timezone, items=[]
        )
    finally:
        # No prompts, provider text, credentials or client contacts in logs.
        logger.info(
            "ai_search status=%s duration_ms=%.0f", status, (perf_counter() - started) * 1000
        )
