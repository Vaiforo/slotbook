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

check:
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen mypy app
	cd backend && uv run --frozen pytest
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

# Starts its own real backend and Vite servers; ports 8000/5173 must be free.
smoke:
	cd frontend && npm run test:smoke
