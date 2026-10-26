"""Run a real API with synthetic data in a disposable PostgreSQL database."""

import os
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from scripts.seed_demo import seed_demo


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
        seed_demo(url)
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
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
