# RealtorNet Backend

FastAPI backend for a real estate platform with authentication, role-based access, audit trails, geospatial property data, analytics views, and background task support.

## Current State
- Current backend version: `0.5.2`
- Phase D backend support is complete
- Supabase Storage uploads/deletes now run through the admin client with explicit MIME metadata and improved error diagnostics
- Amenities catalogue is seeded with 15 residential property amenities
- Deferred tracking currently keeps `DEF-006` and `DEF-007` open; `DEF-008` is resolved on the backend side

## What This Service Provides
- JWT auth with refresh flow and Supabase identity integration
- CRUD APIs for users, agencies, profiles, properties, media, amenities, reviews, inquiries, favorites, and saved searches
- Soft-delete and restore flows with audit fields (`created_by`, `updated_by`, `deleted_by`, `deleted_at`)
- Analytics endpoints backed by database views
- Alembic-based schema migrations (PostgreSQL + PostGIS)
- Celery worker support for async/background jobs

## Tech Stack
- Python 3.10-3.13
- FastAPI, Starlette, Uvicorn
- SQLAlchemy 2.x, Alembic, Psycopg 3, GeoAlchemy2
- PostgreSQL + PostGIS
- Supabase (auth/storage integrations)
- Redis + Celery
- Pytest + pytest-cov

## Project Structure
```text
app/
  api/              # routers and dependencies
  core/             # config, db, security, logging, exceptions
  crud/             # business/data access logic
  db/migrations/    # Alembic migration environment + versions
  models/           # SQLAlchemy models
  schemas/          # Pydantic request/response schemas
  services/         # storage/analytics service-layer logic
  tasks/            # Celery tasks
tests/              # API, CRUD, schema, and core tests
scripts/migrate.py  # migration helper CLI
```

## Script Index Workflow
- Start with [`scriptReferences.md`](scriptReferences.md) before searching through the codebase.
- Keep the index updated whenever script files are added, renamed, removed, or refactored.

## Quick Start

### 1. Clone and create virtual environment
```bash
git clone https://github.com/Orbeenga/realtornet.git
cd realtornet
python -m venv venv
```

Windows PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in repo root.

Required minimum for app startup:
```env
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=realtornet
POSTGRES_PORT=5432
SECRET_KEY=<64+ char random secret>
ENV=development
```

Common optional values:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/realtornet?sslmode=disable
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
REDIS_CELERY_BROKER=redis://localhost:6379/1
REDIS_CELERY_BACKEND=redis://localhost:6379/2
SENTRY_DSN=
DEBUG=true
```

## Run the API
```bash
uvicorn app.main:app --reload
```

Default URLs:
- API base: `http://127.0.0.1:8000/api/v1`
- Swagger docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health check: `http://127.0.0.1:8000/`

## Database Migrations

Run latest migrations:
```bash
alembic upgrade head
```

Create a new migration:
```bash
alembic revision --autogenerate -m "describe change"
```

Rollback one revision:
```bash
alembic downgrade -1
```

Helper script alternatives:
```bash
python scripts/migrate.py run
python scripts/migrate.py create "describe change"
python scripts/migrate.py rollback 1
python scripts/migrate.py current
python scripts/migrate.py history
```

## Running Tests

Run full suite:
```bash
pytest tests/ --tb=short -q
```

Run fast without coverage:
```bash
pytest tests/ --no-cov -q
```

Run with coverage:
```bash
pytest tests/ --tb=short -q
```

Current enforced coverage floor:
- `92.78%` (`pytest.ini` uses `--cov-fail-under=92.78`)

CI/automation notes:
- `make test` and GitHub Actions both run `pytest tests/ --tb=short -q` with the coverage gate provided by `pytest.ini`
- `make test-fast` runs `pytest tests/ --tb=short -q --no-cov`
- `make lint` and GitHub Actions both run `black --check app/ tests/`

Important local test DB note:
- Current `tests/conftest.py` expects PostgreSQL at `localhost:5432` with DB `testdb` and PostGIS available.

## Background Worker (Celery)
```bash
celery -A app.celery_worker worker --loglevel=info --pool=solo --concurrency=1
```

## API Domains
- Auth and admin
- Users, agencies, agent profiles, profiles
- Locations, properties, property types, amenities
- Property images and property amenities
- Favorites, saved searches, inquiries, reviews
- Analytics

## Development Notes
- Use Alembic for schema changes. Do not use `Base.metadata.create_all()` in production workflows.
- Keep audit-trail behavior consistent in CRUD logic.
- Preserve soft-delete semantics (`deleted_at` filters on reads; explicit restore path).

## License
MIT. See [LICENSE](LICENSE).
