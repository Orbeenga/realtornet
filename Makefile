# RealtorNet — Developer task runner
# Usage: make <target>
# Requires: Python venv at ./venv, .env file present

.PHONY: help install dev test test-fast coverage lint migrate migrate-check \
        migrate-history shell health reset-db

# ── Default ──────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "RealtorNet dev commands:"
	@echo ""
	@echo "  make install        Install dependencies from requirements.txt"
	@echo "  make dev            Start development server (uvicorn, reload)"
	@echo "  make test           Run full test suite with coverage"
	@echo "  make test-fast      Run tests without coverage (faster feedback)"
	@echo "  make coverage       Open HTML coverage report in browser"
	@echo "  make lint           Run black format check"
	@echo "  make migrate        Apply all pending Alembic migrations"
	@echo "  make migrate-check  Check for unapplied migrations (CI-safe)"
	@echo "  make migrate-history Show Alembic migration history"
	@echo "  make health         Probe the /health endpoint (server must be running)"
	@echo "  make shell          Open Python shell with app context"
	@echo ""

# ── Environment ───────────────────────────────────────────────────────────────

PYTHON  = ./venv/Scripts/python
PIP     = ./venv/Scripts/pip
PYTEST  = ./venv/Scripts/pytest
UVICORN = ./venv/Scripts/uvicorn
ALEMBIC = ./venv/Scripts/python -m alembic
BLACK   = ./venv/Scripts/black

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -r requirements.txt

# ── Development server ────────────────────────────────────────────────────────

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	$(PYTEST) --tb=short -q

test-fast:
	$(PYTEST) --tb=short -q --no-cov

coverage:
	$(PYTEST) --tb=short -q
	start htmlcov/index.html

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	$(BLACK) --check app/ tests/

# ── Database / Migrations ─────────────────────────────────────────────────────

migrate:
	$(ALEMBIC) upgrade head

migrate-check:
	$(ALEMBIC) current

migrate-history:
	$(ALEMBIC) history --verbose

# ── Health check ──────────────────────────────────────────────────────────────

health:
	curl -s http://localhost:8000/health | python -m json.tool

# ── Shell ─────────────────────────────────────────────────────────────────────

shell:
	$(PYTHON) -c "from app.core.database import engine; from app.core.config import settings; print('RealtorNet shell — DB:', settings.DATABASE_URI[:40], '...')" && $(PYTHON)
