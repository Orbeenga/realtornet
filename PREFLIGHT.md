# PREFLIGHT

Single, unified, DRY, MECE, canonical Phase-2 preflight specification.

## Quick Fix Patterns (Battle-Tested)

1. PostgreSQL ENUM case mismatch
   Problem: Python enum uses `ACTIVE`, DB stores `active`, SQLAlchemy gets confused.
   Solution: `func.lower(cast(Model.status, String)) == value.lower()`.
   Standard: Always use case-insensitive comparison for ENUM filters.
2. SQLAlchemy 2.0 query immutability
   Problem: `query.where()` does not modify the original query; it returns a new object.
   Solution: Always reassign: `query = query.where(...)`.
   Standard: Never orphan query modifications.
3. Identity map cache poisoning
   Problem: Tests read from session cache, not actual DB.
   Solution: `db.flush()` then `db.expire_all()` before assertions.
   Standard: The "Double-Tap" for test isolation.
4. Enum type registration with `values_callable`
   Problem: SQLAlchemy does not know whether to use `.name` or `.value`.
   Solution: Always define:
   `Enum(EnumClass, name="...", values_callable=lambda x: [e.value for e in x])`.
   Standard: Explicit value mapping prevents type confusion.

## Engineering Standards Established

- Case-insensitive ENUM filtering pattern.
- SQLAlchemy 2.0 query immutability handling.
- Identity map cache management in tests.
- Pydantic v2 `.model_dump()` migration standard.
- `values_callable` for all PostgreSQL ENUMs.

## Local Rule: Case-Insensitive Status Filters

Apply case-insensitive filtering to properties and inquiries status filters.
Use `func.lower(cast(Profile.status, String))` for case-insensitive PostgreSQL ENUM filtering.

## Phase-2 Preflight - Unified Canonical Spec (DB <-> ORM)

DRY, MECE, deterministic, ready for reuse.

### 1. Canonical Rules (Always Apply - Global Invariants)

1. Timestamps
   - DB: All creation/update timestamps = `TIMESTAMPTZ DEFAULT now()`.
   - DB: Soft-delete timestamps = `TIMESTAMPTZ DEFAULT NULL` and set only on delete.
   - ORM: `DateTime(timezone=True), server_default=func.now()`.
2. Identifiers
   - Prefer `BIGINT` (Postgres `bigint` / SQLAlchemy `BigInteger`).
   - Use UUID only when public-safe IDs or cross-shard uniqueness is required.
3. FK type parity
   - Every FK column uses the same type as the referenced PK.
4. Naming conventions
   - One global `metadata.naming_convention` defined in `Base`.
5. ENUM parity
   - DB defines all ENUMs.
   - ORM references them with `create_type=False` and exact DB name and values.
6. Geo types
   - Use `Geography(POINT, 4326)` for all location points.
7. Migrations only
   - Never use `Base.metadata.create_all()` in production.
   - Alembic is the only schema management tool.
8. SQLAlchemy 2.x-native
   - No deprecated APIs; consistent sync or async choice.
9. DB is SSOT
   - Database is the single source of truth. ORM always conforms.
10. Soft delete mechanism as default
   - Always use soft delete unless the domain explicitly requires hard delete.
   - Write all delete functions into canonical soft delete mode.
   - Add global mixin: `SoftDeletableModel`.
   - Soft deletion and timestamp sanctity must be enforced globally.
11. Keys must be semantically explicit and domain-qualified at both DB and ORM layers
   - Avoid generic identifiers such as `id`; use `user_id`, `property_id`, etc.
12. Updated-by policy
   - Use `db_obj.updated_by = updated_by_supabase_id`.
   - `updated_at` handled by DB trigger automatically where appropriate.
13. Proper geography handling
   - Use WKT where appropriate, and enforce correct lon/lat ordering.
14. AuditMixin safety decision
   - Use `AuditMixin` everywhere for maximum coverage.
   - `AuditMixin = TimestampMixin + updated_by`.
   - If table missing `updated_by` in DB, column stays NULL; no errors.
   - One-liner: Use `AuditMixin` universally unless a table has `deleted_at` only (then add `SoftDeleteMixin` too).
15. Public error safety
   - Never use `str(e)` or similar methods that can expose internal data in public-facing error responses.
16. Enum usage in tests
   - Tests must never reference uppercase enum members after normalization.
   - Only enum values are stable.

### 2. Database-Side Specification (Schema, Constraints, RLS, Migrations)

#### 2.1 Column and Type Rules

- PKs:
  - BIGINT: `GENERATED ALWAYS AS IDENTITY`
  - UUID: `DEFAULT gen_random_uuid()`
- Timestamps:
  - `created_at timestamptz DEFAULT now()`
  - `updated_at timestamptz DEFAULT now()`
  - Optional: `deleted_at timestamptz`
- ENUM types:
  - Explicit `CREATE TYPE name AS ENUM (...)` in `public`.
- Numeric types:
  - Use `numeric(precision, scale)` for money or surface area (e.g., `numeric(12,2)`).
- Geo:
  - `geography(POINT, 4326)` or `geometry(Point, 4326)`.

#### 2.2 Constraints and Indexes

- CHECK constraints for:
  - Lowercase email, rating ranges, non-negative values, etc.
- Indexes:
  - All FK columns.
  - Common filters.
  - `geom` via GiST.
  - Partial indexes for soft-deleted rows (`WHERE deleted_at IS NULL`).

#### 2.3 RLS and Authentication

- Policies reference `auth.uid()` or `jwt.claims['sub']` to local `supabase_id UUID`.
- Policies expressed minimally using DB columns (`owner_id`, `agency_id`, `is_admin`).

#### 2.4 Migration Rules

- All types (ENUM, PKs, FKs) created or altered explicitly in Alembic.
- Alembic env settings:
  - `include_schemas=True`
  - `compare_type=True`
  - `compare_server_default=True`
- CI:
  - `alembic revision --autogenerate` dry-run diff check.
  - `alembic upgrade --sql` must match expectations.

### 3. ORM and Python Specification

#### 3.1 Base and Metadata

- One global `Base` with unified `metadata = MetaData(naming_convention=...)`.
- Mixins:
  - `TimestampMixin` (created_at, updated_at)
  - `SoftDeleteMixin` (deleted_at)
  - `AuditMixin` (updated_by)
- Mixins must not override values unless DB diverges by design.

#### 3.2 Column Rules

- PKs:
  - `Column(BigInteger, primary_key=True, Identity(always=True))`
  - Or UUID column matching DB.
- Timestamps:
  - `DateTime(timezone=True), server_default=func.now(), nullable=False`.
- FKs:
  - Type = referenced PK type; e.g., `Column(BigInteger, ForeignKey("users.id"))`.
- ENUMs:
  - `ENUM(..., name="enum_name", create_type=False)` matching DB.
- JSONB:
  - `Column(JSONB, nullable=False)` for search or filter payloads.
- Geo:
  - `Column(Geography(geometry_type='POINT', srid=4326))`.

#### 3.3 Relationships

- Use explicit `back_populates`.
- Avoid global eager loading; use per-query `selectinload`.
- `uselist=False` only for true one-to-one DB constraints.

#### 3.4 ORM Hygiene

- No `create_all()`.
- Consistent imports (`BigInteger` vs `Integer`).
- Async or sync uniformly, never mixed arbitrarily.

### 4. Verification Checklist (Pass/Fail Gate for Every Table)

For each table:

1. PK type correct (BIGINT or UUID)?
2. PK identity or default matches canonical spec?
3. All creation and update timestamps use `TIMESTAMPTZ DEFAULT now()` and soft-delete timestamps are NULL by default?
4. ORM timestamps are timezone-aware with `server_default=func.now()`?
5. FK type parity?
6. ENUM names and values matched with `create_type=False`?
7. Geo = `Geography(POINT, 4326)`?
8. Numeric fields correct precision and scale?
9. Naming convention in effect?
10. No `create_all()` usage?
11. Migrations reflect ENUM, FK, and default changes properly?
12. RLS policies reference `supabase_id` and are tested?
13. Indexes exist for FKs, common filters, geom, and partials?
14. No deprecated or mismatched imports or API usage?
15. Public error responses do not expose internal error text (`str(e)` or similar)?

If any fail, remediation is required.

### 5. Remediation Procedure (Deterministic Fix Path)

#### 5.1 Table Creation Flow

1. Create ORM model stub with canonical mixins and types.
2. Create matching Pydantic schemas (Base, Create, Update).
3. Add CRUD operations.
4. Add router endpoint.
5. Run tests.
6. `alembic revision --autogenerate`.
7. Manually inspect for ENUM, DEFAULT, and FK correctness.
8. Apply migration to staging.
9. Run verification checklist.

#### 5.2 Fixing FK Type Mismatches

1. Update ORM to proper type.
2. Alembic migration:
   `ALTER TABLE ... ALTER COLUMN ... TYPE bigint USING ...::bigint`.

#### 5.3 ENUM Mismatches

1. Replace `String` with `ENUM(..., create_type=False)` in ORM.
2. If DB missing ENUM, add via migration.
3. Never drop or recreate ENUMs in production without a safe migration plan.

#### 5.4 Timestamp Inconsistencies

1. Fix ORM to timezone-aware with `server_default=func.now()`.
2. Ensure DB uses `TIMESTAMPTZ DEFAULT now()` and soft-delete timestamps default NULL.

### 6. Alembic and CI Operations

- Alembic env must include:
  - `include_schemas=True`
  - `compare_type=True`
  - `compare_server_default=True`
- CI pipeline must run:
  - Autogen diff check (fail on unexpected).
  - SQL-only upgrade check.
  - Manual approval for type-level changes.

### 7. Optional Automation (Verifier Script)

Recommended script should:

1. Inspect DB (`pg_type`, `pg_enum`, `pg_constraint`, `geometry_columns`).
2. Inspect ORM (`sqlalchemy.inspect`).
3. Produce JSON diff of types, FKs, enums, timestamps, indexes, geo types.
4. Output pass or fail per checklist item.

### 8. Final Operational Notes

- BIGINT for high-growth tables; UUID when IDs must be externally safe.
- Keep migrations backward-compatible.
- Keep AI integrations isolated (`services/ai/`).
- Logs small, structured, rotated.
- Always run the verification checklist before merging DB-affecting change.

## Test Coverage Implementation Guide

Essential rules and patterns for achieving 80%+ test coverage on FastAPI + SQLAlchemy projects.

### 1. Coverage Strategy: Layered Testing

Build test coverage incrementally across multiple test files:

```
v1: Comprehensive baseline (60-70% coverage)
v2: Edge cases and variations (+10-15%)
v3: Surgical targeting of missed lines (+10-15%)
v4: Final cleanup for 85%+
```

Why: Prevents massive unmaintainable test files, allows parallel development, easier debugging.

### 2. Fixture Architecture

ALWAYS centralize fixtures in `conftest.py`.

```python
# Correct: Centralized fixtures
@pytest.fixture
def sample_property(db: Session, normal_user, location, property_type):
    """Reusable across all test files"""
    return property_crud.create(db, obj_in=PropertyCreate(...), user_id=normal_user.user_id)

# Wrong: Duplicating fixtures in each test file
```

Essential fixtures pattern:

```
# Single entity
sample_property

# Multiple entities for filtering/search
multiple_properties  # 4-10 diverse records

# Related entities
property_type, location, user

# Variations
property_type_villa, location_lekki
```

### 3. Transaction Safety

CRITICAL: Use `flush()` not `commit()` in fixtures.

```python
# Correct: Changes persist in transaction, rollback works
@pytest.fixture
def normal_user(db: Session):
    db.flush()  # Persist in transaction

# Wrong: Commits break test isolation
```

Ensure `conftest.py` has transaction rollback:

```python
@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()  # Cleans up after each test
    connection.close()
```

### 4. Input Sanitization (Prevent SQL Errors)

ALWAYS sanitize pagination inputs in CRUD methods:

```python
def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100):
    skip = max(0, skip)
    limit = max(0, limit)

    query = select(Model).offset(skip).limit(limit)
    return db.execute(query).scalars().all()
```

Test for negative inputs:

```python
def test_get_multi_with_negative_skip(db, multiple_records):
    results = crud.get_multi(db, skip=-1, limit=10)
    assert isinstance(results, list)
```

### 5. Geospatial Standards (PostGIS)

Use `Geography(POINT, 4326)` for lat/lon data:

```python
from geoalchemy2 import Geography

class Property(Base):
    geom = Column(Geography(geometry_type='POINT', srid=4326))
```

CRITICAL: WKT coordinate order is LONGITUDE, LATITUDE.

```python
# Correct
WKTElement('POINT(3.3792 6.5244)', srid=4326)  # lon, lat

# Wrong
WKTElement('POINT(6.5244 3.3792)', srid=4326)  # lat, lon
```

Distance units: `ST_DWithin` uses meters for Geography.

```python
radius_meters = radius_km * 1000
ST_DWithin(Property.geom, point, radius_meters)
```

Bounding box order:

```python
# ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, srid)
envelope = ST_MakeEnvelope(3.2, 6.4, 3.5, 6.7, 4326)
```

### 6. Soft Delete Pattern

ALWAYS exclude soft-deleted records in queries:

```python
# Correct
query = select(Property).where(Property.deleted_at.is_(None))

# Wrong: Returns deleted records
```

Soft delete implementation:

```python
def soft_delete(self, db: Session, *, property_id: int):
    stmt = (
        update(Property)
        .where(Property.property_id == property_id)
        .values(deleted_at=func.now())
    )
    db.execute(stmt)
    db.flush()
```

Test soft delete exclusion:

```python
def test_get_multi_excludes_deleted(db, sample_property):
    crud.soft_delete(db, property_id=sample_property.property_id)

    props = crud.get_multi(db, skip=0, limit=100)
    assert sample_property.property_id not in [p.property_id for p in props]
```

### 7. Bulk Operations (Performance)

Use `update().where().values()` for bulk changes:

```python
# Correct: Single SQL command
def bulk_verify(self, db: Session, *, property_ids: List[int]):
    stmt = (
        update(Property)
        .where(Property.property_id.in_(property_ids))
        .values(is_verified=True, verification_date=func.now())
    )
    result = db.execute(stmt)
    db.flush()
    return result.rowcount
```

Test bulk operations:

```python
def test_bulk_update_status(db, multiple_properties):
    prop_ids = [p.property_id for p in multiple_properties[:3]]

    count = crud.bulk_update_status(
        db,
        property_ids=prop_ids,
        new_status=ListingStatus.sold,
    )

    assert count == 3
```

### 8. Filter Implementation

Support optional filters via dict parameter:

```python
def get_multi(
    self,
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
):
    query = select(Property).where(Property.deleted_at.is_(None))

    if filters:
        if "min_price" in filters and filters["min_price"] is not None:
            query = query.where(Property.price >= filters["min_price"])

        if "bedrooms" in filters and filters["bedrooms"] is not None:
            query = query.where(Property.bedrooms == filters["bedrooms"])

        if "is_verified" in filters and filters["is_verified"] is not None:
            query = query.where(Property.is_verified == filters["is_verified"])

    return db.execute(query.offset(skip).limit(limit)).scalars().all()
```

Test all filter combinations:

```python
def test_filter_combined(db, multiple_properties):
    filters = {
        "min_price": 30000000,
        "max_price": 100000000,
        "bedrooms": 3,
        "is_verified": True,
    }

    props = crud.get_multi(db, skip=0, limit=10, filters=filters)
    assert all(30000000 <= p.price <= 100000000 for p in props)
    assert all(p.bedrooms == 3 for p in props)
```

### 9. Test Organization

Use test classes for logical grouping:

```python
class TestPropertyCreate:
    """All creation tests"""
    def test_create_minimal(self, db): ...
    def test_create_complete(self, db): ...
    def test_create_invalid(self, db): ...

class TestPropertyFilters:
    """All filter tests"""
    def test_filter_price(self, db): ...
    def test_filter_bedrooms(self, db): ...
    def test_filter_combined(self, db): ...
```

Naming convention:

```
test_{operation}_{scenario}
test_create_property_minimal_fields
test_get_multi_with_filters
test_bulk_update_status_empty_list
```

### 10. Edge Cases Always Test

Mandatory edge case tests for every CRUD operation:

```
# Empty inputs
test_bulk_operation_empty_list
test_get_multi_with_zero_limit
test_search_with_empty_string

# Invalid inputs
test_operation_with_nonexistent_id
test_operation_with_negative_values
test_operation_with_none_values

# Boundary conditions
test_operation_at_max_limit
test_geospatial_at_poles
test_price_at_zero

# Idempotency
test_delete_already_deleted
test_restore_never_deleted
test_verify_already_verified
```

### 11. Modern Real Estate Features (Required)

Essential features for production real estate platforms:

```python
# GPS Proximity Search
def get_properties_near(
    self, db: Session, *, latitude: float, longitude: float, radius_km: float
):
    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    query = select(Property).where(
        ST_DWithin(Property.geom, point, radius_km * 1000)
    ).order_by(ST_Distance(Property.geom, point))
    return db.execute(query).scalars().all()

# Map Bounding Box Search
def get_properties_in_bounds(
    self, db: Session, *, min_lat: float, min_lon: float,
    max_lat: float, max_lon: float
):
    envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
    query = select(Property).where(Property.geom.ST_Intersects(envelope))
    return db.execute(query).scalars().all()

# Advanced Filtering (PropertyFilter)
# Multi-criteria search (price, bedrooms, type, amenities)

# Bulk Operations
# bulk_verify, bulk_update_status, bulk_soft_delete
```

### 12. Coverage Measurement

Run tests with coverage reporting:

```bash
# Single file
pytest tests/crud/test_properties.py --cov=app/crud/properties --cov-report=term-missing

# Multiple files with wildcard
pytest tests/crud/test_properties_v*.py --cov=app/crud/properties --cov-report=term-missing

# HTML report for detailed analysis
pytest tests/ --cov=app --cov-report=html
```

Interpret missing lines:

```
Missing: 44-63, 139-263
```

Target coverage per file type:

- CRUD: 80-90%
- Models: 90-95%
- Schemas: 85-95%
- API Endpoints: 70-80% (harder due to auth dependencies)
- Utils: 90-95%

### 13. Common Pitfalls to Avoid

- Using `pytest.skip()` for unimplemented features.
- Committing in fixtures (use `flush()`).
- Testing with live database (use transaction rollback).
- Latitude and longitude order confusion (WKT is `POINT(lon lat)`).
- Using km with `ST_DWithin` (convert to meters).
- Forgetting to exclude `deleted_at` (`.where(Model.deleted_at.is_(None))`).
- Hardcoding test data (use parametrization and fixtures).
- Not testing error paths (invalid inputs, not found, permission denied).

### 14. Canonical Compliance Checklist

- Geography(POINT, 4326) for all geospatial data.
- WKT format: `POINT(longitude latitude)`.
- Soft delete on all models (`deleted_at`, `deleted_by`).
- Audit trails (`created_by`, `updated_by` with Supabase IDs).
- UTC timezone for all timestamps.
- No `str(e)` error exposure to users.
- Input validation via Pydantic schemas.
- Transaction-based testing with rollback.
- Coverage target: 80% minimum, 90% ideal.

### 15. PostGIS Antipodal Edge Prevention

Never use exact world boundaries in bounding box queries:

```python
# Wrong: Causes "Antipodal edge detected"
min_lon=-180.0, max_lon=180.0

# Correct: Slightly inside boundaries
min_lon=-179.9, max_lon=179.9
min_lat=-89.9, max_lat=89.9
```

Implement boundary clamping in CRUD:

```python
min_lat = max(-89.9, min(89.9, min_lat))
max_lat = max(-89.9, min(89.9, max_lat))
min_lon = max(-179.9, min(179.9, min_lon))
max_lon = max(-179.9, min(179.9, max_lon))
```

Why: PostGIS Geography cannot handle boxes that wrap exactly 360 degrees around the globe.

### Success Metrics

Session is successful when:

- File coverage increases by 30+ points.
- All tests pass (0 failures).
- No `pytest.skip()` for production features.
- Edge cases covered (empty, invalid, boundary).
- Transaction safety verified (no `commit()` in fixtures).
- Modern features implemented (geospatial, bulk ops, filters).

Project is successful when:

- Overall coverage >= 80%.
- CRUD files >= 85%.
- Models >= 90%.
- Utils >= 90%.
- All canonical rules followed.

Version: 1.0
Last Updated: 2026-02-06
Applies To: FastAPI + SQLAlchemy + PostGIS + Pytest projects

## Engineering Standards and Reusable Skills (Solved Patterns)

1. Database prerequisite initialization
   - Inject PostGIS extensions and custom PostgreSQL enums in test setup before model creation.
2. Strict enum type casting
   - Ensure server_default values are explicitly cast to enum types using `::enum_name`.
3. Model-to-DB fidelity verification
   - Cross-reference SQLAlchemy models against `information_schema` to detect nullability and default mismatches.
4. Hybrid environment configuration
   - Force local PostgreSQL engine for tests while keeping the same schema logic as production.
5. Automated dependency resolution
   - Explicitly import related models in tests to register metadata for FKs.
6. Namespace and collection error resolution
   - Centralize helper functions in `tests/utils/__init__.py` to avoid deep-path import fragility.
7. Dynamic slug and collision logic validation
   - Use UUID suffixes to validate get-or-create branches for slug uniqueness.
8. Deterministic geospatial benchmarking
   - Distinguish coverage artifacts caused by test collection interruptions.
9. Environmental path forcing
   - Use `PYTHONPATH="."` to prioritize local source tree on Windows.

## Standards Table

| Standard | Implementation Rule |
| --- | --- |
| Testing Strategy | Use surgical tests for new features; move to comprehensive suites only after hitting >80% coverage. |
| DRY Imports | Expose all test helpers via `tests/utils/__init__.py` to avoid deep-path import fragility. |
| MECE Coverage | Run coverage reports using explicit `--cov=app.module` flags to ensure no logic branch is ignored. |
| Conflict Handling | Use `--ignore` flags during collection if peripheral API errors block core CRUD validation. |

## Audit Trail

| table_name | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| --- | --- | --- | --- | --- | --- | --- |
| agencies | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| agent_profiles | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| favorites | created_at | n/a | updated_at | n/a | deleted_at | deleted_by |
| inquiries | created_at | n/a | updated_at | n/a | deleted_at | deleted_by |
| locations | created_at | n/a | updated_at | updated_by | deleted_at | deleted_by |
| profiles | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| properties | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| reviews | created_at | n/a | updated_at | n/a | deleted_at | deleted_by |
| saved_searches | created_at | n/a | updated_at | n/a | deleted_at | deleted_by |
| users | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |

## Next Actual Work (First Real Schema Change)

Example: add `bio` field to `User` model.

1. Edit `app/models/users.py`:

```python
bio = Column(Text, nullable=True)
```

2. Generate migration:

```
alembic revision --autogenerate -m "add_user_bio_field"
```

3. Review the file.
4. Apply it:

```
alembic upgrade head
```

5. Done.

## Policy: Create Skills From Solved Problems

For any interaction where we have solved a problem and I share the results, call it out and immediately add it as a skill or markdown document for reuse.