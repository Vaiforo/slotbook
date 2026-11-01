"""Inspect delivery state or explicitly retry one failed event, without printing contacts."""

import argparse
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import NotificationDelivery, OutboxEvent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "retry"])
    parser.add_argument("--event-id", type=UUID)
    args = parser.parse_args()
    engine = create_engine(Settings().database_url)
    try:
        with Session(engine) as db, db.begin():
            if args.action == "retry":
                if args.event_id is None:
                    parser.error("--event-id is required for retry")
                # Same lock order as dispatcher: event, then delivery.
                event = db.scalar(
                    select(OutboxEvent).where(OutboxEvent.id == args.event_id).with_for_update()
                )
                row = db.scalar(
                    select(NotificationDelivery)
                    .where(NotificationDelivery.event_id == args.event_id)
                    .with_for_update()
                )
                if event is None or row is None or row.status != "failed":
                    raise SystemExit("Only an existing failed delivery can be retried")
                row.status, row.attempts, row.last_error = "pending", 0, None
                row.next_attempt_at = event.next_publish_at = db.scalar(
                    select(func.clock_timestamp())
                )
                print("Retry scheduled")
            else:
                for row in db.scalars(
                    select(NotificationDelivery)
                    .order_by(NotificationDelivery.next_attempt_at.desc())
                    .limit(100)
                ):
                    print(row.event_id, row.status, row.attempts, row.last_error or "-")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
