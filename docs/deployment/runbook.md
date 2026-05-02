# RealtorNet — Deployment Runbook

**Last updated:** 2026-03-29  
**Alembic head:** `6c0087f609b4`  
**Coverage floor:** 92.78%  

---

## 1. Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11 or 3.12 | Runtime |
| Docker | 24+ | Local PostGIS database |
| Git | any | Source control |
| psql | any | DB verification queries |

Accounts required:
- Supabase project (production DB + storage + auth)
- GitHub repository access
- (Optional) Sentry DSN for error monitoring
- (Optional) SendGrid account for transactional email

---

## 2. Local Development Bootstrap

### 2.1 Clone and configure

```bash
git clone https://github.com/Orbeenga/realtornet.git
cd realtornet
cp .env.example .env
# Edit .env — fill in all YOUR_* placeholders
```

### 2.2 Create virtual environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2.3 Start local PostGIS (Docker)

```bash
docker run -d \
  --name local-postgis \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  postgis/postgis:15-3.3
```

Verify:
```bash
docker ps | grep local-postgis
```

### 2.4 Run migrations

```bash
# Confirm migration state
python -m alembic current

# Apply all pending migrations
python -m alembic upgrade head

# Confirm at head
python -m alembic current
# Expected: latest repo revision marked "(head)"
```

### 2.5 Start development server

```bash
# Via Makefile (recommended)
make dev

# Direct
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.6 Verify locally

```bash
# Root health check
curl http://localhost:8000/

# DB connectivity probe
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","version":"2.0"}
```

### 2.7 Run test suite

```bash
make test
# Expected: 1683+ passing, 1 skip, 0 failures, coverage >= 92.78%
```

---

## 3. Production Environment Variables

All variables below are required in production. No defaults are safe to use.

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Supabase pooler connection string | `postgresql+psycopg://postgres.PROJECT_ID:PASSWORD@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require` |
| `DIRECT_URL` | Same as DATABASE_URL for this setup | same as above |
| `SECRET_KEY` | JWT signing key — 64+ hex chars | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry | `15` |
| `ENV` | Environment name | `production` |
| `SUPABASE_URL` | Supabase project URL | `https://PROJECT_ID.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon key | from Supabase dashboard |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | from Supabase dashboard |
| `BACKEND_CORS_ORIGINS` | Allowed frontend origins | `["https://yourdomain.com"]` |
| `REDIS_URL` | Preferred Redis connection string for Railway backend service | `${{Redis.REDIS_URL}}` |
| `REDISHOST` / `REDISPORT` / `REDISUSER` / `REDISPASSWORD` | Railway Redis component variables, also supported by backend config | Reference from the Railway Redis service when `REDIS_URL` is not shared |
| `REDIS_HOST` | Legacy Redis host fallback | `localhost` or managed Redis host |
| `REDIS_PORT` | Legacy Redis port fallback | `6379` |
| `PYTHONPATH` | Module resolution | `.` |

Optional but recommended:
| Variable | Description |
|---|---|
| `SMTP_HOST` | Transactional email SMTP host |
| `SMTP_PORT` | SMTP port |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `SENDGRID_API_KEY` | SendGrid API key |
| `MAIL_FROM` | Verified sender address |
| `EMAIL_DELIVERY_MODE` | `sync` for single-process Railway deploys; `celery` only when a worker is deployed |
| `EMAIL_DRY_RUN` | `false` in production, `true` for non-delivery dry runs |
| `FRONTEND_BASE_URL` | Frontend URL used in email CTA links |

---

## 4. Production Deployment

### 4.1 Pre-deployment checklist

Run through this before every production deployment:

- [ ] All tests passing locally: `make test`
- [ ] Production DB migrated before traffic: `python -m alembic upgrade head`
- [ ] No unapplied migrations: `python -m alembic current` shows latest repo head
- [ ] `.env` production values verified — no placeholder values
- [ ] `ENV=production` set in production environment
- [ ] `SECRET_KEY` is 64+ hex characters, unique to production
- [ ] `BACKEND_CORS_ORIGINS` lists only production frontend domains
- [ ] Supabase production project is separate from dev project

### 4.2 Deploy steps

```bash
# 1. Pull latest
git pull origin main

# 2. Install/update dependencies
pip install -r requirements.txt

# 3. Apply migrations (production DB)
# Confirm current state first
python -m alembic current

# Apply
python -m alembic upgrade head

# Confirm head
python -m alembic current

# If this deploy added a migration file, verify newly mapped columns before
# browser traffic is considered live. A code deploy with an old schema can
# break unrelated routes such as login because SQLAlchemy loads all mapped
# columns during user fetches.
python - <<'PY'
from sqlalchemy import create_engine, inspect
from app.core.config import settings

engine = create_engine(settings.DATABASE_URI)
inspector = inspect(engine)
print([column["name"] for column in inspector.get_columns("users")])
print([column["name"] for column in inspector.get_columns("agencies")])
PY

# 4. Restart application server
# Via systemd:
sudo systemctl restart realtornet

# Via process manager (gunicorn/uvicorn):
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 5. Verify deployment
curl https://yourdomain.com/health
# Expected: {"status":"healthy","database":"connected","version":"2.0"}
```

### 4.3 Post-deployment verification

```bash
# Health probe
curl https://yourdomain.com/health

# API root
curl https://yourdomain.com/api/v1/

# Auth endpoint reachable
curl -X POST https://yourdomain.com/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=wrongpassword"
# Expected: 401 Unauthorized (confirms auth stack is live)
```

---

## 5. Rollback Procedure

### 5.1 Code rollback

```bash
# Identify last known good commit
git log --oneline -10

# Roll back to previous commit
git checkout <previous-commit-hash>
pip install -r requirements.txt
sudo systemctl restart realtornet
```

### 5.2 Migration rollback

```bash
# List migration history
python -m alembic history --verbose

# Roll back one revision
python -m alembic downgrade -1

# Roll back to specific revision
python -m alembic downgrade <revision_id>

# Confirm state
python -m alembic current
```

> ⚠️ Always test downgrade() in staging before running against production.
> Every migration in this repo has a downgrade() function — verify it is correct before deploying.

---

## 6. Database Management

### 6.1 Migration workflow

```bash
# Generate new migration (never use --autogenerate blindly — review output)
python -m alembic revision -m "description_of_change"

# Review generated file in app/db/migrations/versions/
# Apply
python -m alembic upgrade head
```

### 6.2 Known migration notes

- `env.py` filters suppress `ix_` vs `idx_` index naming differences — cosmetic only
- PostGIS columns handled via custom `render_item()` in `env.py`
- `alembic check` hangs on Supabase/PostGIS schemas — do not use
- Alembic connects via service role which bypasses RLS

### 6.3 Supabase-specific

- Port `6543` = pooler (PgBouncer) — use for application connections
- Port `5432` = direct — use only if pooler is unavailable
- RLS is enforced for all `anon` and `authenticated` roles
- `active_properties` and `agent_performance` views are restricted to `service_role` only
- `alembic_version` table has RLS enabled with deny-all policy (intentional)

---

## 7. CI/CD

CI runs on every push to `main` and `develop` via `.github/workflows/ci.yml`.

Pipeline steps:
1. Spin up PostGIS 15-3.3 service container
2. Install dependencies
3. Verify migration framework (`alembic current`)
4. Run full test suite with coverage gate (floor: 92.78%)
5. Black format check (hard failure)

Matrix: Python 3.11 and 3.12.

To run CI checks locally before pushing:
```bash
make test
make lint
python -m alembic current
```

---

## 8. Observability

### 8.1 Logs

- Development: text format, rotating file at `logs/realtornet_YYYYMMDD.log`
- Production: JSON format on stdout (parse with log aggregator), text format in file

Log file rotation: 10 MB per file, 5 backups retained.

### 8.2 Health endpoint

`GET /health` — returns DB connectivity status. Use as deployment readiness probe.

```json
{"status": "healthy", "database": "connected", "version": "2.0"}
```

Returns `503` if DB is unreachable.

### 8.3 Error monitoring (recommended)

Sentry is not yet integrated. To add:
```bash
pip install sentry-sdk[fastapi]
```

Add to `app/main.py`:
```python
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
```

Add `SENTRY_DSN` to `.env` and `.env.example`.

---

## 9. Known Issues and Deferred Items

| Item | Status | Notes |
|---|---|---|
| Postgres version 15.8.1.106 | Upgrade pending | Do via Supabase dashboard at low-traffic moment |
| `update_updated_at_column` trigger | External DB change | Applied directly in Supabase, not in Alembic — documented in CHANGELOG.md |
| Unused index report (104 indexes) | Deferred | Revisit after 30 days production traffic |
| Full-text / trigram search | Deferred | Current ILIKE search functional; upgrade after traffic data available |
| GIN indexes | Deferred | Depends on search strategy decision |
| `test_auth.py` freezegun skip | Closed | Fixed in v0.4.6 |
| `get_within_radius_approved` pagination test | Closed | Fixed in v0.4.6 |

---

## 10. Tag History

| Tag | What landed |
|---|---|
| `v0.4.1-alembic-baseline` | Alembic baseline, revision `ccf073c8b981` |
| `v0.4.2-perf-indexes` | 11 duplicate indexes/constraints dropped |
| `v0.4.3-perf-python-aggregations` | Agent property queries rewritten to SQL |
| `v0.4.4-perf-pagination` | Shared pagination dependency, `le=100` cap |
| `v0.4.5-security-pass` | Views secured, RLS hardened, trigger hardened |
| `v0.4.6-test-coverage` | Token expiration + spatial pagination tests |
