# PROJECT_TRUTH

Read-only factual audit of the current repository state for `RealtorNet`.
Date audited: 2026-03-29 (Africa/Lagos)

## 1) REPO SHAPE
### Top-Level Shape (observed)
| Category | Items | Evidence |
|---|---|---|
| Core app dirs | `app/`, `tests/`, `scripts/`, `docs/`, `static/` | `Get-ChildItem -Name` |
| Infra/meta dirs | `.github/`, `.claude/`, `.github_old_realtorconnect/`, `.git_backup_realtorconnect/` | `Get-ChildItem -Name` |
| Generated/runtime dirs present | `.pytest_cache/`, `htmlcov/`, `logs/`, `venv/`, `realtornet.egg-info/` | `Get-ChildItem -Name` |
| Key root files | `README.md`, `requirements.txt`, `pyproject.toml`, `pytest.ini`, `alembic.ini`, `CHANGELOG.md` | `Get-ChildItem -Name` |

### Key Application Folders
| Folder | Present | Notes | Evidence |
|---|---|---|---|
| `app/api` | Yes | Routers + dependencies | `app/` directory listing |
| `app/core` | Yes | config/security/db/logging | `app/` directory listing |
| `app/crud` | Yes | 14 domain CRUD modules + `__init__.py` | `app/crud` file listing |
| `app/models` | Yes | 16 model files + base/init | `app/models` file listing |
| `app/schemas` | Yes | 16 schema files + base/init | `app/schemas` file listing |
| `app/services` | Yes | `analytics_services.py`, `storage_services.py` | `app/services` file listing |

### Test Folders
| Folder | Python files | Evidence |
|---|---:|---|
| `tests/api` | 19 | scripted count |
| `tests/crud` | 33 | scripted count |
| `tests/core` | 2 | scripted count |
| `tests/schemas` | 8 | scripted count |
| `tests/services` | 1 | scripted count |
| `tests/e2e` | 1 | scripted count |
| `tests/utils` | 2 | scripted count |

### Infra/DevOps Files
| File | Present | Evidence |
|---|---|---|
| `.github/workflows/ci.yml` | Yes | `.github/workflows` listing |
| `Dockerfile` | No | existence check |
| `docker-compose.yml` / `.yaml` | No | existence check |
| `Makefile` | No | existence check |
| `.env.example` | No | existence check |
| `Procfile` | No | existence check |

### Scripts
| Script | Present | Evidence |
|---|---|---|
| `scripts/check_backend.sh` | Yes | `scripts` listing |
| `scripts/migrate.py` | Yes | `scripts` listing |
| `scripts/run_e2e.sh` | Yes | `scripts` listing |
| `scripts/test_target.sh` | Yes | `scripts` listing |

### Docs
| Doc area | Files found | Evidence |
|---|---|---|
| `docs/agent-workflows` | `browser-validation.md`, `session-discipline.md` | recursive docs listing |
| `docs/review` | `pr-review-checklist.md` | recursive docs listing |

## 2) RUNTIME ENTRYPOINTS
| Item | Current truth | Evidence |
|---|---|---|
| App startup file | `app/main.py` creates FastAPI app | `app/main.py` |
| ASGI/WGI entrypoint | ASGI app object: `app` in `app/main.py`; `uvicorn.run(...)` under `if __name__ == "__main__"` | `app/main.py` |
| Router registration root | `app.include_router(api_router, prefix=settings.API_V1_STR)` | `app/main.py` |
| Additional direct router include | `app.include_router(analytics.router, prefix="/api")` | `app/main.py` |
| Router map source | centralized in `app/api/api.py` via `api_router.include_router(...)` | `app/api/api.py` |
| Middleware registration | `CORSMiddleware`, then `RedisRateLimitMiddleware` | `app/main.py` |
| Dependency injection hub | `app/api/dependencies.py` (`get_db`, auth/role deps, pagination dep) | `app/api/dependencies.py` |

### Contradiction/Drift Signals
| Signal | Observation | Evidence |
|---|---|---|
| Duplicate analytics registration pathing | `analytics.router` included in `api_router` (prefix `/analytics`) and again directly in `main.py` (prefix `/api`) | `app/api/api.py`, `app/main.py` |
| Version prefix comment drift | `api.py` docstring says `/api/realtornet/v1`; config uses `/api/v1` | `app/api/api.py`, `app/core/config.py` |

## 3) DATABASE TRUTH
### ORM Inventory
- 16 model files (+ `base.py`, `__init__.py`) under `app/models`.
- Core entities present: users, agencies, profiles, agent_profiles, properties, locations, inquiries, reviews, favorites, saved_searches, property types/images/amenities.
- Analytics view models present in `app/models/analytics.py`.

Evidence: `app/models` file listing.

### Alembic Presence + History
| Item | Truth | Evidence |
|---|---|---|
| Alembic config present | Yes (`alembic.ini`) | root file listing |
| Migration env | Present (`app/db/migrations/env.py`) | file exists |
| Versioned migrations | 9 files under `app/db/migrations/versions` | versions listing |
| Includes SQL migration | `20250610_add_rls_policies.sql` | versions listing |

### Naming Convention Usage
| Truth | Evidence |
|---|---|
| Global SQLAlchemy naming convention defined in `app/models/base.py` (`ix`, `uq`, `ck`, `fk`, `pk`) | `app/models/base.py` |

### Enum Usage (DB-facing)
| Model | Enum mechanism | Evidence |
|---|---|---|
| `users` | `SQLAEnum(UserRole, name="user_role_enum", values_callable=...)` | `app/models/users.py` |
| `properties` | PostgreSQL `ENUM(ListingType/listing_status, create_type=False)` | `app/models/properties.py` |
| `inquiries` | `SQLEnum(InquiryStatus, name='inquiry_status_enum', create_type=False)` | `app/models/inquiries.py` |
| `profiles` | `Enum(ProfileStatus, name="profile_status_enum", values_callable=...)` | `app/models/profiles.py` |

### Timestamp Conventions
| Truth | Evidence |
|---|---|
| `TimestampMixin` defines `created_at`/`updated_at` with `server_default=func.now()` | `app/models/base.py` |
| Most models inherit mixins (`TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`) | model imports and class declarations in `app/models/*.py` |
| `updated_at` trigger behavior assumed in CRUD comments (not universally centralized in one file) | multiple CRUD comments (e.g., `app/crud/inquiries.py`, `app/crud/reviews.py`) |

### Soft Delete Conventions
| Truth | Evidence |
|---|---|
| `SoftDeleteMixin` provides `deleted_at`, `deleted_by` | `app/models/base.py` |
| CRUD layer heavily filters `deleted_at.is_(None)` and defines `soft_delete` paths per entity | `app/crud/*.py` grep results |

### DB Session Management
| Truth | Evidence |
|---|---|
| Sync SQLAlchemy engine + session factory in `app/core/database.py` | `app/core/database.py` |
| FastAPI DB dependency is generator `get_db()` | `app/core/database.py` |
| `init_db()`/`drop_db()` with `Base.metadata.create_all/drop_all` restricted to `settings.TESTING` | `app/core/database.py` |

### DB-first vs Code-first Drift Signals
| Signal | Observation | Evidence |
|---|---|---|
| Migration filters hide many naming/style differences | `include_object()` excludes legacy idx/fkey/key patterns | `app/db/migrations/env.py` |
| Project claims DB-first; test-only `create_all()` still exists (guarded) | `init_db()` exists for tests only | `app/core/database.py` |

## 4) AUTH + SECURITY
| Topic | Truth | Evidence |
|---|---|---|
| Auth endpoints | `/auth/login`, `/auth/refresh`, `/auth/register`, `/auth/me` | `app/api/endpoints/auth.py` |
| Token creation/validation | JWT issue/decode/refresh in `app/core/security.py` | `app/core/security.py` |
| Password hashing | bcrypt (`get_password_hash`, `verify_password`) | `app/core/security.py` |
| Supabase integration points | client helpers in `app/utils/supabase_client.py`; config keys in `app/core/config.py` | those files |
| Role/permission deps | `get_current_admin_user`, `get_current_agent_user`, `get_current_active_user`, etc. | `app/api/dependencies.py` |
| Request-size guard | `validate_request_size` dependency (10MB cap) | `app/api/dependencies.py` |
| Storage/security touchpoints | bucket whitelist + safe filename + image resizing in storage service | `app/services/storage_services.py` |
| Security drift signal | `print(...)` debug statements in auth dependency path | `app/api/dependencies.py` |

## 5) API SURFACE
### Routers + Prefixes (registered)
- `auth`, `admin`, `users`, `agencies`, `agent-profiles`, `profiles`, `locations`, `properties`, `property-types`, `amenities`, `property-amenities`, `property-images`, `favorites`, `saved-searches`, `inquiries`, `reviews`, `analytics`.

Evidence: `app/api/api.py`.

### Endpoint Count by Module
| Module | Total | GET | POST | PUT | PATCH | DELETE |
|---|---:|---:|---:|---:|---:|---:|
| admin.py | 14 | 6 | 4 | 2 | 0 | 2 |
| agencies.py | 8 | 5 | 1 | 1 | 0 | 1 |
| agent_profiles.py | 9 | 6 | 1 | 1 | 0 | 1 |
| amenities.py | 7 | 4 | 1 | 1 | 0 | 1 |
| analytics.py | 9 | 9 | 0 | 0 | 0 | 0 |
| auth.py | 4 | 1 | 3 | 0 | 0 | 0 |
| favorites.py | 8 | 4 | 2 | 0 | 0 | 2 |
| inquiries.py | 12 | 6 | 3 | 1 | 1 | 1 |
| locations.py | 9 | 6 | 1 | 1 | 0 | 1 |
| profiles.py | 6 | 2 | 2 | 1 | 0 | 1 |
| properties.py | 8 | 5 | 1 | 1 | 0 | 1 |
| property_amenities.py | 6 | 1 | 2 | 1 | 0 | 2 |
| property_images.py | 7 | 2 | 2 | 2 | 0 | 1 |
| property_types.py | 6 | 3 | 1 | 1 | 0 | 1 |
| reviews.py | 12 | 6 | 2 | 2 | 0 | 2 |
| saved_searches.py | 6 | 2 | 2 | 1 | 0 | 1 |
| users.py | 7 | 3 | 1 | 2 | 0 | 1 |

Evidence: scripted `@router.<method>(` count over `app/api/endpoints/*.py`.

### Health/Readiness
| Endpoint | Present | Notes | Evidence |
|---|---|---|---|
| `/` root health-like endpoint | Yes | returns status/message/version; no DB probe | `app/main.py` |
| `/health` explicit endpoint | No | no route match under API modules | grep over `app/api` + `app/main.py` |

### Analytics Surface
- Dedicated `analytics` router with 9 GET endpoints (view-based + metrics endpoints).
- Also mounted directly with different prefix in `main.py` (see drift note above).

Evidence: `app/api/endpoints/analytics.py`, `app/api/api.py`, `app/main.py`.

## 6) CRUD + SERVICE LAYER
### CRUD Inventory
- 14 CRUD modules with method counts ranging from 8 to 43 functions.
- Largest module: `properties.py` (43 functions), indicating concentration of logic.

Evidence: `app/crud` listing + scripted function count.

### Service Inventory
| Service module | Purpose signal | Evidence |
|---|---|---|
| `analytics_services.py` | analytics computations + view queries | `app/services/analytics_services.py` |
| `storage_services.py` | upload/resize/delete with Supabase storage | `app/services/storage_services.py` |

### Repeated Patterns
| Pattern | Where observed | Evidence |
|---|---|---|
| Soft-delete filtering | pervasive in CRUD queries | `app/crud/*.py` grep `deleted_at` |
| Pagination (skip/limit) | frequent endpoint-to-CRUD pass-through | endpoint files |
| Role checks at endpoint level | repeated dependency wiring per endpoint file | `app/api/endpoints/*.py` + `app/api/dependencies.py` |

### Cross-layer Leakage Signals
| Signal | Observation | Evidence |
|---|---|---|
| Business/control logic in routers | many endpoints build conditional branch logic beyond transport concerns | e.g., `app/api/endpoints/properties.py`, `admin.py` |
| DB access outside CRUD | dependencies call direct `db.query(...)` for auth user resolution | `app/api/dependencies.py` |

## 7) SCHEMAS + CONTRACTS
### Schema Inventory
- 16 schema files plus `__init__.py`.
- Typical Create/Update/Response triads exist for core entities.

Evidence: `app/schemas` listing + scripted class-name pattern counts.

### Pattern Consistency Snapshot
| File | Create classes | Update classes | Response classes | Total classes |
|---|---:|---:|---:|---:|
| properties.py | 1 | 1 | 3 | 9 |
| users.py | 1 | 1 | 2 | 9 |
| reviews.py | 2 | 1 | 5 | 10 |
| stats.py | 0 | 0 | 8 | 13 |
| token.py | 0 | 0 | 0 | 3 |

Evidence: scripted schema class count over `app/schemas/*.py`.

### Enum/Value Contract Alignment Signals
| Observation | Evidence |
|---|---|
| DB enum names explicitly referenced in models (`*_enum`) | `app/models/users.py`, `properties.py`, `inquiries.py`, `profiles.py` |
| `values_callable` used in some enums | `users.py`, `profiles.py` |

## 8) TESTING TRUTH
| Topic | Truth | Evidence |
|---|---|---|
| Test runner | pytest configured via `pytest.ini` | `pytest.ini` |
| Coverage gate | `--cov-fail-under=92.78` | `pytest.ini` |
| Test inventory | 69 Python test files under `tests/` | scripted test count |
| Test distribution | CRUD-heavy (`tests/crud`: 33 files), API-heavy (`tests/api`: 19 files) | scripted dir counts |
| Skip markers still present | explicit `pytest.skip(...)` cases in `tests/crud/test_properties_v3.py` | grep over tests |
| Fixture foundation | dense fixtures in `tests/conftest.py` incl. geospatial points and multi-entity fixtures | `tests/conftest.py` |

## 9) OPERATIONS READINESS
| Area | Current truth | Evidence |
|---|---|---|
| CI pipeline | Single workflow `ci.yml` runs install + tests + optional black check | `.github/workflows/ci.yml` |
| Migration safety in CI | No explicit Alembic migration step/check in CI file | `.github/workflows/ci.yml` |
| Logging strategy | Standard Python logging with text formatter + rotating file handler | `app/core/logging.py` |
| Structured JSON logging | Not present in logging module | `app/core/logging.py` |
| Health/readiness endpoint | Root endpoint exists, no dedicated readiness/DB check endpoint | `app/main.py` |
| Metrics/telemetry hooks | no Sentry/Prometheus/OpenTelemetry references found in app/CI/docs scan | grep results |
| Env var contract artifact | settings contract exists in code, but no `.env.example` file | `app/core/config.py`, existence check |
| Deployment runbook | no dedicated deploy/runbook docs found in `docs/` set | docs listing |

## 10) SEARCH + PERFORMANCE
| Area | Evidence-based truth | Evidence |
|---|---|---|
| Search style in code | Predominantly `ilike` + `%term%` patterns in CRUD | `app/crud/agencies.py`, `agent_profiles.py`, `amenities.py`, `locations.py` |
| PostgreSQL full-text usage | No `to_tsvector`, `to_tsquery`, `plainto_tsquery` usage found in app `crud/api` scan | grep results |
| Known text target columns | `properties.description`, `agent_profiles.bio`, `inquiries.message` are `Text` columns | `app/models/properties.py`, `agent_profiles.py`, `inquiries.py` |
| Perf work evidence | migration exists for dropping duplicate indexes | `app/db/migrations/versions/20260328_0308-6c0087f609b4_perf_drop_duplicate_indexes.py` |
| Hotspot likely for later EXPLAIN | wide query logic concentrated in `app/crud/properties.py` (43 methods) | scripted CRUD function count |

## 11) KNOWN GAPS / MISSING BUILDING BLOCKS
| Gap | Evidence |
|---|---|
| Missing `.env.example` | existence check: false |
| Missing local task orchestrator (`Makefile`) | existence check: false |
| Missing container orchestration files (`Dockerfile`, `docker-compose`) | existence checks: false |
| No explicit `/health` or readiness endpoint contract | `app/main.py` root-only health route |
| No structured JSON logging baseline | `app/core/logging.py` text formatter |
| Debug `print` statements in auth dependency path | `app/api/dependencies.py` |
| CI lacks migration verification step | `.github/workflows/ci.yml` |
| Duplicate analytics router registration pattern | `app/api/api.py` and `app/main.py` |

## 12) FINAL VERDICT
### Current Project Phase (evidence-based)
- Backend domain/API/CRUD/test coverage is mature and actively maintained.
- Operational packaging and deployment contract artifacts are partially present.

### Closed / Strongly Established
| Domain | Status | Evidence |
|---|---|---|
| Core backend architecture | Established | full module inventories in `app/` |
| CRUD/API breadth | Established | endpoint + CRUD counts |
| Test + coverage discipline | Established | `pytest.ini` 92.78 gate + large tests tree |
| Alembic migration framework | Established | `app/db/migrations/*`, version history |

### Partially Closed
| Domain | Status | Evidence |
|---|---|---|
| Health/observability | Partial | root health route exists; no dedicated readiness/metrics pipeline |
| CI/CD hardening | Partial | CI runs tests, but no migration/deploy safety stages |
| Environment reproducibility | Partial | code-side settings contract exists; no `.env.example` |

### Not Yet Production-Ready (from repository artifacts)
| Area | Why | Evidence |
|---|---|---|
| Deployment ergonomics | no Docker/compose/Makefile/runbook artifacts in repo | existence checks + docs listing |
| Operational observability standardization | no structured logging/telemetry integration surfaced | `app/core/logging.py`, grep for sentry/prometheus/otel |
| Readiness contract | no explicit DB-backed readiness endpoint documented/exposed | route scans |

### Recommended Next Phase (planning only)
- Create an **operations contract phase** focused on reproducible bootstrap artifacts (`.env.example`, bootstrap command), readiness/health checks, structured logging baseline, and CI migration safety checks.

