"""Reject a release with inconsistent application/package/contract versions."""

import json
import tomllib
from pathlib import Path

from app import __version__

root = Path(__file__).resolve().parents[2]
backend = tomllib.loads((root / "backend/pyproject.toml").read_text())
lock = tomllib.loads((root / "backend/uv.lock").read_text())
frontend = json.loads((root / "frontend/package.json").read_text())
npm_lock = json.loads((root / "frontend/package-lock.json").read_text())
versions = {
    "app": __version__,
    "pyproject": backend["project"]["version"],
    "uv.lock": next(p["version"] for p in lock["package"] if p["name"] == "slotbook-backend"),
    "package.json": frontend["version"],
    "package-lock.json": npm_lock["version"],
    "npm root package": npm_lock["packages"][""]["version"],
    "OpenAPI": json.loads((root / "docs/openapi.json").read_text())["info"]["version"],
}
if len(set(versions.values())) != 1:
    raise SystemExit(f"Application versions differ: {versions}")
if f"## {__version__} " not in (root / "CHANGELOG.md").read_text():
    raise SystemExit("Missing CHANGELOG entry for the application version")
print(f"Application version: {__version__}")
