"""Run continuously alongside the API; recover missed Wednesdays after downtime."""

import argparse
import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.catalog.schedule import LOCK_ID, extend_due, initialize_schedule, today_in_omsk
from app.core.config import Settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def run_once(engine: Engine) -> dict[str, int]:
    with Session(engine) as db, db.begin():
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.execute(text("SET LOCAL statement_timeout = '30s'"))
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_ID}):
            return {"weeks_extended": 0, "slots_created": 0, "slots_skipped": 0}
        today = today_in_omsk(db)
        state = initialize_schedule(db, today)
        if state is None:
            return {"weeks_extended": 0, "slots_created": 0, "slots_skipped": 0}
        return extend_due(db, state, today)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
    try:
        while True:
            try:
                result = run_once(engine)
                if result["weeks_extended"] or args.once:
                    logger.info("catalog_schedule %s", result)
            except Exception:
                if args.once:
                    raise
                logger.exception("catalog_schedule_failed")
            if args.once:
                return
            time.sleep(60)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
