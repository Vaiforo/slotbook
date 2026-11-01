import logging
from uuid import UUID

import httpx
from sqlalchemy import create_engine

from app.core.config import Settings
from app.notifications.delivery import deliver
from app.notifications.queue import celery

logger = logging.getLogger(__name__)


@celery.task(name="slotbook.deliver")  # type: ignore[untyped-decorator]
def deliver_event(event_id: str) -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        with httpx.Client(timeout=httpx.Timeout(10, connect=3), follow_redirects=False) as client:
            status = deliver(engine, settings, UUID(event_id), client)
        logger.log(
            logging.WARNING if status == "failed" else logging.INFO,
            "notification %s %s",
            event_id,
            status,
        )
    except Exception:
        # Never let Celery log SQL bound contacts or HTTP credentials in a traceback.
        logger.error("notification %s processing_failed", event_id)
        # Unfinished deliveries are recovered by the dispatcher sweep.
    finally:
        engine.dispose()
