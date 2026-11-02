"""Contract-fixture eval by default; --live evaluates synthetic prompts with the provider."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.client import HTTPModelClient, LLMUnavailable
from app.ai.schemas import Preference
from app.ai.service import Clarification, reserve_call, window
from app.core.config import Settings


def evaluate(raw: str | None, now: datetime, timezone: str) -> dict[str, str]:
    try:
        if raw is None:
            raise LLMUnavailable()
        preference = Preference.model_validate_json(raw)
        start, end = window(preference, now, timezone)
        return {
            "status": "window",
            "date": start.date().isoformat(),
            "time_from": start.strftime("%H:%M"),
            "time_to": end.strftime("%H:%M"),
        }
    except Clarification as exc:
        return {"status": "clarification", "reason": exc.reason}
    except LLMUnavailable, ValidationError:
        return {"status": "unavailable"}


async def run(live: bool) -> None:
    cases = json.loads((Path(__file__).resolve().parents[1] / "evals/slot_search.json").read_text())
    settings = Settings()
    if live and not settings.ai_model:
        raise SystemExit("Live eval requires configured model/key/Redis and migrated PostgreSQL.")
    engine = create_async_engine(settings.database_url) if live else None
    sessions = async_sessionmaker(engine) if engine else None
    results = []
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as http:
            client = HTTPModelClient(http, settings)
            for case in cases:
                now = datetime.fromisoformat(case["now"]).astimezone(ZoneInfo(case["timezone"]))
                source = "fixture"
                output = case["output"]
                raw = json.dumps(output) if isinstance(output, dict) else output
                if live and case["live"]:
                    assert sessions is not None
                    async with sessions() as session:
                        if not await reserve_call(session, settings.ai_daily_request_limit):
                            raise SystemExit("Daily AI budget exhausted; no further requests made.")
                    source = "provider"
                    try:
                        raw = await client.extract(case["text"], now, case["timezone"])
                    except LLMUnavailable:
                        raw = None
                actual = evaluate(raw, now, case["timezone"])
                results.append(
                    {
                        "id": case["id"],
                        "source": source,
                        "passed": actual == case["expected"],
                        "actual": actual,
                        "expected": case["expected"],
                    }
                )
    finally:
        if engine:
            await engine.dispose()
    print(
        json.dumps(
            {
                "mode": "live" if live else "contract-fixtures",
                "model": settings.ai_model if live else None,
                "passed": sum(r["passed"] for r in results),
                "total": len(results),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Spends up to 20 reserved provider calls"
    )
    asyncio.run(run(parser.parse_args().live))
