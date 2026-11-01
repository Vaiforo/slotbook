import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import NotificationDelivery, OutboxEvent

logger = logging.getLogger(__name__)


def dispatch_one(engine: Engine, publish: Callable[[str], None]) -> bool:
    with Session(engine) as db, db.begin():
        event = db.scalar(
            select(OutboxEvent)
            .join(NotificationDelivery)
            .where(
                NotificationDelivery.status.in_(["pending", "retrying"]),
                NotificationDelivery.next_attempt_at <= func.clock_timestamp(),
                OutboxEvent.next_publish_at <= func.clock_timestamp(),
            )
            .order_by(OutboxEvent.created_at)
            .with_for_update(skip_locked=True, of=OutboxEvent)
            .limit(1)
        )
        if event is None:
            return False
        publish(str(event.id))
        now = cast(datetime, db.scalar(select(func.clock_timestamp())))
        event.published_at = now
        # Periodic redelivery also recovers a lost retry or worker failure.
        event.next_publish_at = now + timedelta(seconds=30)
    return True


def main() -> None:
    from app.notifications.queue import celery

    engine = create_engine(Settings().database_url, pool_pre_ping=True)

    def publish(event_id: str) -> None:
        celery.send_task(
            "slotbook.deliver", args=[event_id], task_id=event_id, retry=False, timeout=5
        )

    try:
        while True:
            try:
                if dispatch_one(engine, publish):
                    continue
            except Exception:
                logger.error("notification_dispatch_failed")
            time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
