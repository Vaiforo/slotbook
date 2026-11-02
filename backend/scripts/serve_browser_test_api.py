"""Run a real API with synthetic data in a disposable PostgreSQL database."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.ai.client import LLMUnavailable
from app.ai.router import get_llm
from app.core.config import Settings
from app.main import create_app
from app.models import Specialist, User
from app.modules.owner.security import hasher
from scripts.seed_demo import seed_demo


def create_browser_app():
    """Deterministic LLM fixture ONLY for the disposable browser-test runner."""
    settings = Settings()
    if settings.environment != "test":
        raise RuntimeError("Browser fixtures require test environment")
    app = create_app(settings)

    class BrowserLLM:
        async def extract(self, text: str, now: datetime, timezone: str) -> str:
            if text == "Сбой провайдера":
                raise LLMUnavailable()
            if text == "Медленный ответ":
                await asyncio.sleep(1)
            ambiguous = text == "Завтра после трёх"
            return json.dumps(
                {
                    "date": (now.date() + timedelta(days=1)).isoformat(),
                    "time_from": "10:00",
                    "time_to": "12:00",
                    "needs_clarification": ambiguous,
                    "reason": "time" if ambiguous else None,
                }
            )

    app.dependency_overrides[get_llm] = BrowserLLM
    return app


def main() -> None:
    admin_url = make_url(os.getenv("SLOTBOOK_TEST_ADMIN_URL", Settings().database_url))
    name = "slotbook_browser_" + uuid4().hex
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    child: subprocess.Popen[bytes] | None = None

    def stop(signum: int, frame: object) -> None:
        if child is not None:
            child.terminate()
        else:
            raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    created = False
    try:
        with engine.connect() as conn:
            if not str(conn.scalar(text("SHOW server_version_num"))).startswith("18"):
                raise RuntimeError("Browser tests require PostgreSQL 18")
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        url = admin_url.set(database=name).render_as_string(hide_password=False)
        os.environ["SLOTBOOK_DATABASE_URL"] = url
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        # Credentials exist only inside this disposable browser-test database.
        seed_demo(url, password="browser-owner-password")
        fixture_engine = create_engine(url)
        try:
            with Session(fixture_engine) as session, session.begin():
                other = User(
                    normalized_email="other@example.invalid",
                    password_hash=hasher.hash("browser-other-password"),
                )
                session.add(other)
                session.flush()
                session.add(
                    Specialist(
                        user_id=other.id,
                        slug="other",
                        display_name="Другой специалист",
                        timezone="Asia/Omsk",
                    )
                )
        finally:
            fixture_engine.dispose()
        os.environ["SLOTBOOK_AI_MODEL"] = ""
        os.environ["SLOTBOOK_AI_API_KEY"] = ""
        os.environ["SLOTBOOK_REDIS_URL"] = ""
        os.environ["SLOTBOOK_ENVIRONMENT"] = "test"
        os.environ["SLOTBOOK_PUBLIC_ORIGIN"] = "http://127.0.0.1:5173"
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "scripts.serve_browser_test_api:create_browser_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ]
        )
        code = child.wait()
        if code not in (0, -signal.SIGTERM):
            raise SystemExit(code)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        if created:
            with engine.connect() as conn:
                conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        engine.dispose()


if __name__ == "__main__":
    main()
