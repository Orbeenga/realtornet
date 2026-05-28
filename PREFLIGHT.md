# PREFLIGHT

Single, unified, DRY, MECE, canonical engineering specification.
Applies to the full RealtorNet stack: FastAPI · SQLAlchemy · PostGIS · Supabase · Next.js · Pytest.

**Version:** 2.0
**Last Updated:** May 2026
**Status:** Active — supersedes v1.0 (February 2026)

---

## Quick Fix Patterns (Battle-Tested)

1. **PostgreSQL ENUM case mismatch**
   Problem: Python enum uses `ACTIVE`, DB stores `active`, SQLAlchemy gets confused.
   Solution: `func.lower(cast(Model.status, String)) == value.lower()`.
   Standard: Always use case-insensitive comparison for ENUM filters.

2. **SQLAlchemy 2.0 query immutability**
   Problem: `query.where()` does not modify the original query; it returns a new object.
   Solution: Always reassign: `query = query.where(...)`.
   Standard: Never orphan query modifications.

3. **Identity map cache poisoning**
   Problem: Tests read from session cache, not actual DB.
   Solution: `db.flush()` then `db.expire_all()` before assertions.
   Standard: The "Double-Tap" for test isolation.

4. **Enum type registration with `values_callable`**
   Problem: SQLAlchemy does not know whether to use `.name` or `.value`.
   Solution: Always define:
   `Enum(EnumClass, name="...", values_callable=lambda x: [e.value for e in x])`.
   Standard: Explicit value mapping prevents type confusion.

5. **PostGIS geography column — ALTER EXTENSION blocked**
   Problem: `ALTER EXTENSION postgis SET SCHEMA extensions` fails when any table has a `geography` or `geometry` column type.
   Solution: Clean-slate provisioning — new Supabase project with PostGIS installed in `extensions` schema before any migrations run.
   Standard: PostGIS must be installed in `extensions` schema at project initialization. Cannot be relocated after geography columns exist.

6. **Supabase PgBouncer/Supavisor drops `ALTER DATABASE` search_path**
   Problem: `ALTER DATABASE postgres SET search_path TO public, extensions` is not honoured by connection pooler endpoints.
   Solution: Pin search_path to roles as well:
   ```sql
   ALTER ROLE postgres SET search_path TO public, extensions;
   ALTER ROLE authenticated SET search_path TO public, extensions;
   ALTER ROLE anon SET search_path TO public, extensions;
   ALTER ROLE service_role SET search_path TO public, extensions;
   ```
   Standard: Always pin both database and roles when using a non-public extension schema.

7. **psycopg3 prepared statement corruption (dev only)**
   Problem: Repeated queries against same connection corrupt prepared statement cache.
   Solution: `prepare_threshold=None` in engine config.
   Standard: Set `prepare_threshold=None` in dev; monitor in production.

---

## Canonical Rules (Always Apply — Global Invariants)

1. **Timestamps**
   - DB: All creation/update timestamps = `TIMESTAMPTZ DEFAULT now()`.
   - DB: Soft-delete timestamps = `TIMESTAMPTZ DEFAULT NULL` and set only on delete.
   - ORM: `DateTime(timezone=True), server_default=func.now()`.

2. **Identifiers**
   - Prefer `BIGINT GENERATED ALWAYS AS IDENTITY` for all application tables (high-growth, internal, FK-safe).
   - Use UUID only when IDs must be externally safe or cross-shard unique (e.g. invite tokens, public-facing references).
   - Never use plain `INTEGER` — use `BIGINT` to avoid overflow at scale.
   - Column names must be semantically explicit and domain-qualified: `user_id`, `property_id`, `agency_id` — never bare `id`.

3. **FK type parity**
   Every FK column uses the same type as the referenced PK. `BIGINT` FK → `BIGINT` PK; `UUID` FK → `UUID` PK. No mixing.

4. **Naming conventions**
   One global `metadata.naming_convention` defined in `Base`. Never deviate per-table.

5. **ENUM parity**
   DB defines all ENUMs. ORM references them with `create_type=False` and exact DB name and values. Never add ENUM values without an Alembic migration.

6. **Geo types**
   Use `Geography(POINT, 4326)` for all location points. Never `geometry` unless specifically required by a PostGIS function.
   WKT coordinate order is always LONGITUDE, LATITUDE — `POINT(lon lat)`.

7. **Migrations only**
   Never use `Base.metadata.create_all()` in any environment.
   Alembic is the only schema management tool. Every schema change goes through a migration.

8. **SQLAlchemy 2.x-native**
   No deprecated APIs. Consistent sync or async — never mixed arbitrarily in the same request path.

9. **DB is SSOT**
   Database is the single source of truth. ORM conforms to DB. API types conform to ORM. Frontend types are generated from OpenAPI — never manually written for API response shapes.

10. **Soft delete as default**
    Always soft delete unless the domain explicitly requires hard delete (e.g. test data cleanup).
    Global mixin: `SoftDeletableModel` with `deleted_at TIMESTAMPTZ`.
    All queries must filter `WHERE deleted_at IS NULL` unless explicitly auditing deleted records.

11. **Updated-by policy**
    Use `db_obj.updated_by = updated_by_supabase_id`.
    `updated_at` handled by DB trigger automatically.

12. **AuditMixin universally**
    `AuditMixin = TimestampMixin + SoftDeleteMixin + updated_by`.
    Apply to all tables unless they are append-only audit tables (which never update or delete).

13. **Append-only audit tables**
    `agent_membership_audit` is the canonical example: no UPDATE, no DELETE, ever.
    Enforce via trigger: `prevent_agent_membership_audit_mutation`.
    Trigger functions must use `SET search_path = ''` to prevent schema injection.

14. **Public error safety**
    Never use `str(e)` or similar in public-facing error responses.
    Health endpoints return fixed strings — never exception text.

15. **Enum usage in tests**
    Tests must never reference uppercase enum members after normalization.
    Only enum values (lowercase strings) are stable references.

16. **Function search path safety**
    All custom PostgreSQL functions must include `SET search_path = ''` between the volatility modifier and `AS $$`.
    This prevents search path injection via mutable schema resolution.

---

## Extension Schema Standard

**PostGIS must be installed in the `extensions` schema, never `public`.**

### Initialization sequence (new Supabase project — must run before any migrations):

```sql
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION postgis WITH SCHEMA extensions;
ALTER DATABASE postgres SET search_path TO public, extensions;
ALTER ROLE postgres    SET search_path TO public, extensions;
ALTER ROLE authenticated SET search_path TO public, extensions;
ALTER ROLE anon        SET search_path TO public, extensions;
ALTER ROLE service_role SET search_path TO public, extensions;
```

### Verification (run after initialization, before Alembic):

```sql
-- Must return 0 rows. If any rows returned, PostGIS is in public schema — do not proceed.
SELECT ext.extname, c.relname
FROM pg_depend d
JOIN pg_extension ext ON d.refobjid = ext.oid
JOIN pg_class c ON d.objid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = 'public' AND d.deptype = 'e';
```

### Why this cannot be fixed after the fact:
Once any table has a `geography` or `geometry` column, `ALTER EXTENSION postgis SET SCHEMA extensions` is blocked by PostgreSQL type dependency constraints. The only remediation is clean-slate provisioning. This was discovered in Phase K (May 2026) when the production Supabase project was initialized without this sequence.

---

## Database-Side Specification

### Column and Type Rules

- PKs: `BIGINT GENERATED ALWAYS AS IDENTITY`
- External-safe IDs: `UUID DEFAULT gen_random_uuid()`
- Timestamps: `created_at TIMESTAMPTZ DEFAULT now()`, `updated_at TIMESTAMPTZ DEFAULT now()`, optional `deleted_at TIMESTAMPTZ`
- ENUM types: Explicit `CREATE TYPE name AS ENUM (...)` in `public`
- Numeric types: `NUMERIC(precision, scale)` for money or area — e.g. `NUMERIC(12,2)`
- Geo: `GEOGRAPHY(POINT, 4326)` — installed via `CREATE EXTENSION postgis WITH SCHEMA extensions`

### Constraints and Indexes

- CHECK constraints for: lowercase email, rating ranges, non-negative values
- Indexes on: all FK columns, common filter columns, `geom` via GiST, partial indexes for soft-delete (`WHERE deleted_at IS NULL`)

### RLS Rules

- Enable RLS on all application tables before any public traffic
- Policies reference `auth.uid()` mapped to `supabase_id UUID` on the local `users` table
- Extension metadata tables (e.g. `spatial_ref_sys`) must have RLS enabled with a deny-all policy if they land in `public`
- PostGIS internal functions (`st_estimatedextent` etc.) must have `EXECUTE` revoked from `anon` and `authenticated`
- Append-only audit tables get RLS: authenticated users can read own records; no INSERT/UPDATE/DELETE via API

### Migration Rules

- All types (ENUM, PKs, FKs) created or altered explicitly in Alembic
- Alembic env settings: `include_schemas=True`, `compare_type=True`, `compare_server_default=True`
- `preDeployCommand = "alembic upgrade head"` in `railway.toml` — migrations run automatically on every Railway deploy
- Never accumulate unapplied migrations — run gates after every meaningful change
- ENUM values: use `ADD VALUE` migration; never drop and recreate in production

---

## ORM and Python Specification

### Base and Metadata

- One global `Base` with unified `metadata = MetaData(naming_convention=...)`
- Mixins: `TimestampMixin` (created_at, updated_at), `SoftDeleteMixin` (deleted_at), `AuditMixin` (updated_by)
- Mixins must not override values unless DB diverges by design

### Column Rules

- PKs: `Column(BigInteger, primary_key=True, Identity(always=True))`
- External-safe IDs: UUID column matching DB
- Timestamps: `DateTime(timezone=True), server_default=func.now(), nullable=False`
- FKs: type = referenced PK type — `Column(BigInteger, ForeignKey("users.user_id"))`
- ENUMs: `ENUM(..., name="enum_name", create_type=False)` matching DB exactly
- JSONB: `Column(JSONB, nullable=False)` for search or filter payloads
- Geo: `Column(Geography(geometry_type='POINT', srid=4326))`

### Relationships

- Use explicit `back_populates`
- Avoid global eager loading; use per-query `selectinload`
- `uselist=False` only for true one-to-one DB constraints

---

## Role Model (Locked — Phase G onwards)

| Role | Source | Core Capability |
|---|---|---|
| `seeker` | Public signup | Browse, inquire, favourite, save searches, write reviews |
| `agent` | Agency invitation or admin override | Create/manage listings, receive inquiries |
| `agency_owner` | Admin approval of agency application | All agent capabilities + invite/govern own agency roster |
| `admin` | Internal only | Full platform governance |

### JWT Invalidation via role_version

When a user's role is demoted (e.g. last membership revoked → seeker), `role_version` is incremented atomically on the `users` row. JWT middleware compares the token's `role_version` claim against the DB value on every authenticated request. Mismatch returns 401, triggering silent refresh with the new role and version.

---

## Membership Audit Standard

`agent_membership_audit` is append-only. Actions: `invited / joined / suspended / revoked / left / reinstated`.
Every membership state change writes a record with `actor_id`, `reason`, `prior_role`, `post_role`.
Last-membership revocation must atomically: count active memberships → if zero, set `user_role = seeker` and increment `role_version` → write REVOKED audit record → all in one transaction.

---

## Email Standard (Resend)

- Email service: Resend
- `MAIL_FROM` must be a verified sender domain — never `onboarding@resend.dev` in production
- All email tasks are fail-open: a Resend failure never blocks the primary endpoint action
- Email tasks fire async but are testable via sync `.apply()` mode in `EMAIL_DELIVERY_MODE=sync`
- Required email types: inquiry received → agent, moderation outcome → agent, role change → user, agency approval/rejection → applicant, agent invitation → invitee, saved search match → seeker

---

## Location / Geocoding Standard (Nominatim)

- All geocoding is server-side only — never direct from browser
- Nominatim public API: descriptive User-Agent, 1 req/sec throttle, 5-minute in-memory cache
- `GET /api/v1/locations/search?q=` is the frontend's only geocoding surface
- Location results must filter to Nigeria (`country_code = 'ng'`) to prevent global pollution of the location DB
- Frontend appends context to search terms to improve result quality (e.g. "Lekki Lagos" not "Lekki")
- `GET /api/v1/locations/search?q=` is the only geocoding surface

---

## Frontend Standards

- Framework: Next.js App Router, TypeScript strict mode
- No `fetch()` calls in components — all API calls via TanStack Query hooks
- API types from `src/types/api.generated.ts` only — generated via `pnpm gen:types` from live backend OpenAPI schema. Never manually write interfaces for API response shapes.
- Run `pnpm gen:types` after every backend schema change before any frontend work
- Auth: Supabase Auth JS SDK manages session. Silent JWT refresh on 401: intercept → refresh → retry once → logout.
- State: server state in TanStack Query, URL state in Next.js router searchParams, global UI in Zustand, form state in React Hook Form
- Validation: Zod schemas mirror Pydantic models — field names and types must match
- No inline styles — Tailwind classes only
- No hardcoded strings for labels, routes, messages — use constants files
- Navigation contract lives in `navigation.ts` — do not hardcode route strings elsewhere

---

## Verification Checklist (Pass/Fail Gate for Every Table)

1. PK type correct — BIGINT with `GENERATED ALWAYS AS IDENTITY`?
2. PK identity or default matches canonical spec?
3. All creation and update timestamps use `TIMESTAMPTZ DEFAULT now()`? Soft-delete timestamps NULL by default?
4. ORM timestamps timezone-aware with `server_default=func.now()`?
5. FK type parity — every FK is same type as referenced PK?
6. ENUM names and values matched with `create_type=False`?
7. Geo columns use `Geography(POINT, 4326)`?
8. Numeric fields use correct precision and scale?
9. Naming convention in effect — no bare `id` columns?
10. No `create_all()` usage anywhere?
11. Migrations reflect ENUM, FK, and default changes properly?
12. RLS enabled on all application tables?
13. Indexes exist for FKs, common filters, geom (GiST), and partial soft-delete?
14. No deprecated or mismatched imports or API usage?
15. Public error responses do not expose internal error text?
16. All custom functions have `SET search_path = ''`?
17. PostGIS confirmed in `extensions` schema — Query A/B/C return 0 rows in `public`?
18. Email tasks fail-open — primary action not blocked by email failure?
19. `pnpm gen:types` run after any backend schema change?
20. `tsc --noEmit`, `lint`, `build` all passing on frontend?
21. `pyright` 0 errors, `pytest ≥ 95%` coverage on backend?

---

## Remediation Procedure

### Table Creation Flow

1. Create ORM model stub with canonical mixins and types
2. Create matching Pydantic schemas (Base, Create, Update, Response)
3. Add CRUD operations
4. Add router endpoint
5. Run tests
6. `alembic revision --autogenerate`
7. Manually inspect for ENUM, DEFAULT, and FK correctness
8. Apply migration to staging
9. Run verification checklist

### New Production Project Provisioning (Clean-Slate Protocol)

Required when: PostGIS schema drift is detected in an existing project, or when initializing any new production Supabase project.

1. Create new Supabase project
2. Run Extension Isolation Sequence (see above) in Supabase SQL editor before any migrations
3. Verify with Query A/B/C — must return 0 rows
4. Point local `.env` at new project credentials
5. Run `alembic upgrade head` — all migrations apply fresh
6. Run `pyright` + `pytest ≥ 95%` against new DB
7. Re-register real user accounts via the UI (Option A — no hardcoded UUIDs in migrations)
8. Update Railway env vars, redeploy Railway first, confirm `/healthz` returns 200
9. Update Vercel env vars, redeploy Vercel
10. Run 12-journey smoke test
11. Archive old project for 30 days as cold backup before deletion
12. Update all CLAUDE.md files with new project ID

### Fixing FK Type Mismatches

1. Update ORM to proper type
2. Alembic migration: `ALTER TABLE ... ALTER COLUMN ... TYPE bigint USING ...::bigint`

### ENUM Mismatches

1. Replace `String` with `ENUM(..., create_type=False)` in ORM
2. If DB missing ENUM, add via migration
3. Never drop or recreate ENUMs in production without a safe migration plan

---

## Test Coverage Standards

### Coverage Targets (Current — Phase K onwards)

- Overall: ≥ 95% (enforced via `--cov-fail-under=95.0`)
- CRUD: ≥ 90%
- Models: ≥ 90%
- Schemas: ≥ 90%
- API Endpoints: ≥ 85%
- Utils: ≥ 90%
- Email tasks: ≥ 80%
- Storage services: ≥ 80%

### Coverage Strategy: Layered Testing

```
v1: Comprehensive baseline (60-70% coverage)
v2: Edge cases and variations (+10-15%)
v3: Surgical targeting of missed lines (+10-15%)
v4: Final cleanup for 95%+
```

### Transaction Safety

CRITICAL: Use `flush()` not `commit()` in fixtures.

```python
@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

### Geospatial Standards

```python
# WKT coordinate order: LONGITUDE first, then LATITUDE
WKTElement('POINT(3.3792 6.5244)', srid=4326)  # lon=3.3792, lat=6.5244

# Distance units: ST_DWithin uses meters for Geography
radius_meters = radius_km * 1000

# Bounding box: ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, srid)
envelope = ST_MakeEnvelope(3.2, 6.4, 3.5, 6.7, 4326)

# Antipodal edge prevention: never use exact world boundaries
min_lon = max(-179.9, min(179.9, min_lon))
max_lon = max(-179.9, min(179.9, max_lon))
min_lat = max(-89.9, min(89.9, min_lat))
max_lat = max(-89.9, min(89.9, max_lat))
```

### Mandatory Edge Cases

Every CRUD operation must test: empty inputs, bulk operations on empty list, get with zero limit,
search with empty string, nonexistent ID, negative values, none values, max limit boundary,
geospatial at poles, price at zero, idempotency (delete already deleted, restore never deleted).

---

## Audit Trail (Current Table Inventory)

| Table | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
|---|---|---|---|---|---|---|
| agencies | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| agent_membership_audit | ✅ | n/a | n/a (append-only) | n/a | n/a (never) | n/a |
| agent_profiles | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| agency_agent_memberships | ✅ | n/a | ✅ | n/a | ✅ | ✅ |
| favorites | ✅ | n/a | ✅ | n/a | ✅ | ✅ |
| inquiries | ✅ | n/a | ✅ | n/a | ✅ | ✅ |
| locations | ✅ | n/a | ✅ | ✅ | ✅ | ✅ |
| properties | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| property_types | ✅ | n/a | ✅ | n/a | ✅ | n/a |
| reviews | ✅ | n/a | ✅ | n/a | ✅ | ✅ |
| saved_searches | ✅ | n/a | ✅ | n/a | ✅ | n/a |
| users | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## CI Pipeline (Both Repos — Required on Every PR)

**Backend:**
```bash
pyright           # 0 errors required
pytest --cov-fail-under=95.0   # all passing, ≥ 95% coverage
```

**Frontend:**
```bash
pnpm exec tsc --noEmit   # 0 errors
pnpm lint                 # 0 warnings
pnpm build                # 0 warnings
```

**After any backend schema change:**
```bash
pnpm gen:types   # regenerate src/types/api.generated.ts from live OpenAPI
```

---

## Common Pitfalls

- Using `pytest.skip()` for unimplemented features
- Committing in fixtures (use `flush()`)
- Testing with live database (use transaction rollback)
- Latitude and longitude order confusion — WKT is `POINT(lon lat)`, not `POINT(lat lon)`
- Using km with `ST_DWithin` — convert to meters
- Forgetting to exclude soft-deleted records — always `WHERE deleted_at IS NULL`
- Installing PostGIS in `public` schema instead of `extensions`
- Running `ALTER EXTENSION postgis SET SCHEMA extensions` after geography columns exist — it will hard-fail
- Forgetting to pin search_path to roles as well as database when using non-public extension schema
- Writing `str(e)` in any public-facing error response
- Manually writing TypeScript interfaces for API response shapes instead of running `gen:types`
- Touching `apiClient.ts` auth intercept logic without explicitly re-verifying silent JWT refresh
- Removing existing UI sections instead of adding alongside them

---

## Policy: Create Skills From Solved Problems

For any interaction where a problem has been solved and results shared, immediately add it as a skill or entry in this document for reuse. The pattern that burned us once must be documented so it never burns us again.
