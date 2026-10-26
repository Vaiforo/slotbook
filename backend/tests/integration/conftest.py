import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="module")
def database():
    if not os.getenv("SLOTBOOK_TEST_ADMIN_URL"):
        pytest.skip("SLOTBOOK_TEST_ADMIN_URL is required for PostgreSQL tests")
    # Always create our own random database. Never downgrade or drop the supplied database.
    admin_url = make_url(os.environ["SLOTBOOK_TEST_ADMIN_URL"])
    name = "slotbook_test_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        assert conn.scalar(text("SHOW server_version_num"))[:2] == "18"
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = admin_url.set(database=name).render_as_string(hide_password=False)
    old = os.environ.get("SLOTBOOK_DATABASE_URL")
    os.environ["SLOTBOOK_DATABASE_URL"] = url
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        command.check(cfg)
        yield url
    finally:
        if old is None:
            os.environ.pop("SLOTBOOK_DATABASE_URL", None)
        else:
            os.environ["SLOTBOOK_DATABASE_URL"] = old
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
