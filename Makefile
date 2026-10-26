export UV_CACHE_DIR := $(CURDIR)/.cache/uv
export UV_PYTHON_INSTALL_DIR := $(CURDIR)/.cache/python
export npm_config_cache := $(CURDIR)/.cache/npm

.PHONY: install backend frontend check smoke

install:
	cd backend && uv sync --frozen
	cd frontend && npm ci

backend:
	cd backend && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log

frontend:
	cd frontend && npm run dev

check: api-check
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen mypy app
	cd backend && uv run --frozen pytest
	cd frontend && npm run lint
	cd frontend && npm run test:unit
	cd frontend && npm run typecheck
	cd frontend && npm run build

# Starts its own real backend and Vite servers; ports 8000/5173 must be free.
smoke:
	cd frontend && npm run test:smoke

.PHONY: db-up db-stop migrate seed db-test

db-up:
	docker compose up -d --wait db

db-stop:
	docker compose stop db

migrate:
	cd backend && uv run --frozen alembic upgrade head

seed:
	cd backend && uv run --frozen python -m scripts.seed_demo

# Creates and drops ONLY a new random slotbook_test_* database.
# Override for a dedicated PostgreSQL 18 server with CREATEDB permission.
SLOTBOOK_TEST_ADMIN_URL ?= postgresql+psycopg://slotbook:slotbook_local_only@127.0.0.1:5432/slotbook
db-test:
	cd backend && SLOTBOOK_TEST_ADMIN_URL="$(SLOTBOOK_TEST_ADMIN_URL)" uv run --frozen pytest tests/integration

.PHONY: api-generate api-check
api-generate:
	cd backend && uv run --frozen python -m scripts.export_openapi
	cd frontend && npm run api:generate

api-check:
	cd backend && uv run --frozen python -m scripts.export_openapi --check
	cd frontend && npm run api:check
