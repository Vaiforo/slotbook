from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

import httpx
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Booking, NotificationDelivery, OutboxEvent, Slot
from app.notifications.provider import DeliveryError, backoff, send


def deliver(engine: Engine, settings: Settings, event_id: UUID, client: httpx.Client) -> str:
    with Session(engine) as db, db.begin():
        row = db.scalar(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.event_id == event_id, NotificationDelivery.channel == "email"
            )
            .with_for_update()
        )
        if row is None or row.status in {"sent", "failed"}:
            return "ignored"
        now = cast(datetime, db.scalar(select(func.clock_timestamp())))
        if row.next_attempt_at > now:
            return "waiting"
        event = db.get(OutboxEvent, event_id)
        assert event is not None
        booking = db.get(Booking, event.booking_id)
        assert booking is not None
        slot = db.get(Slot, booking.slot_id)
        assert slot is not None
        row.attempts += 1
        subject = "Запись создана" if event.kind == "booking_created" else "Запись отменена"
        message = (
            f"{subject}. Время встречи (UTC): {slot.starts_at.isoformat()}. "
            f"Событие: {event.created_at.isoformat()}. "
            "Секретная ссылка предоставляется отдельно на странице записи."
        )
        try:
            send(
                client,
                settings.email_url,
                settings.email_api_key,
                str(event.id),
                booking.client_email,
                subject,
                message,
            )
        except DeliveryError as error:
            row.last_error = error.code
            if error.retryable and row.attempts < settings.notification_max_attempts:
                row.status = "retrying"
                row.next_attempt_at = cast(
                    datetime, db.scalar(select(func.clock_timestamp()))
                ) + timedelta(seconds=backoff(row.attempts, error.delay))
            else:
                row.status = "failed"
        else:
            row.status = "sent"
            row.delivered_at = db.scalar(select(func.clock_timestamp()))
            row.last_error = None
        return row.status
