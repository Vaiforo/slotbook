"""Deterministic export; no engine, lifespan, or database connection is needed."""

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("../docs/openapi.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app = create_app(Settings(_env_file=None, app_name="SlotBook"))
    content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise SystemExit("OpenAPI is stale: run make api-generate")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)


if __name__ == "__main__":
    main()
