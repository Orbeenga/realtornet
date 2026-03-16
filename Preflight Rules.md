 here is a unstructured compilation of standards we've been using throughout this project it comprises of core learnings we encountered along the way. please keep all these in mind as we work here:
📋 Core Learnings (Battle-Tested Standards)
1. PostgreSQL ENUM Case Mismatch
Problem: Python Enum uses ACTIVE, DB stores 'active', SQLAlchemy gets confused
Solution: func.lower(cast(Model.status, String)) == value.lower()
Standard: Always use case-insensitive comparison for ENUM filters
2. SQLAlchemy 2.0 Query Immutability
Problem: query.where() doesn't modify original, returns new object
Solution: Always reassign: query = query.where(...)
Standard: Never orphan query modifications
3. Identity Map Cache Poisoning
Problem: Tests read from session cache, not actual DB
Solution: db.flush() then db.expire_all() before assertions
Standard: The "Double-Tap" for test isolation
4. Enum Type Registration with values_callable
Problem: SQLAlchemy doesn't know whether to use .name or .value
Solution: Always define: Enum(EnumClass, name="...", values_callable=lambda x: [e.value for e in x])
Standard: Explicit value mapping prevents type confusion


Engineering Standards Established

Case-insensitive ENUM filtering pattern
SQLAlchemy 2.0 query immutability handling
Identity map cache management in tests
Pydantic v2 .model_dump() migration
values_callable for all PostgreSQL ENUMs
 


Apply case-insensitive filtering to properties and inquiries status filters
use func.lower(cast(Profile.status, String)) for case-insensitive PostgreSQL ENUM filtering.


1. Canonical Rules and guiding document
 **single, unified, DRY, MECE, canonical Phase-2 preflight specification**.
This is now ready to **save and reuse** as your permanent standard.

---

# **PHASE-2 PREFLIGHT — UNIFIED CANONICAL SPEC (DB ↔ ORM)**

*(DRY, MECE, deterministic, ready for reuse)*

---

# **1. Canonical Rules (Always Apply — Global Invariants)**

1. **Timestamps**

   * **DB:** “All creation/update timestamps = TIMESTAMPTZ DEFAULT now()
    	      Soft-delete timestamps = TIMESTAMPTZ DEFAULT NULL and set only on delete.”
   * **ORM:** `DateTime(timezone=True), server\_default=func.now()`.

2. **Identifiers**

   * Prefer **BIGINT** (Postgres `bigint` / SQLAlchemy `BigInteger`).
   * Use **UUID** only when public-safe IDs or cross-shard uniqueness required.

3. **FK Type Parity**

   * Every FK column uses the **same type** as the referenced PK.

4. **Naming Conventions**

   * One global `metadata.naming\_convention` defined in `Base`.

5. **ENUM Parity**

   * DB defines all ENUMs.
   * ORM references them with `create\_type=False` and exact DB name/values.

6. **Geo Types**

   * Use `Geography(POINT, 4326)` for all location points.

7. **Migrations Only**

   * **Never** use `Base.metadata.create\_all()` in production.
   * Alembic is the *only* schema management tool.

8. **SQLAlchemy 2.x-Native**

   * No deprecated APIs; consistent sync/async choice.

9. **DB is SSOT**

   * Database is the single source of truth. ORM always conforms.

10. **Soft Delete Mechanism as Default

* Always use soft delete as default delete mechanism except where not appropriate
in which we case we can use hard delete or some other appropriate mechanism.
* Write all delete functions into canonical soft delete mode
✔ Add global mixin: SoftDeletableModel.
* soft deletion & timestamp sanctity must be enforced globally.

11. **Keys must be semantically explicit and domain-qualified at both DB and ORM layers, that is for example instead of the generic "id" for user must use the proper reference "user_id" Avoid generic identifiers

12. ** use db_obj.updated_by = updated_by_supabase_id
        # updated_at handled by DB trigger automatically where appropriate
13. Proper geography handling as wkt where appropriate accordingly.


14. ** AuditMixin Safety Decision
✅ YES - Use AuditMixin everywhere for maximum coverage
Why:

AuditMixin = TimestampMixin + updated_by column
If table missing updated_by in DB → Column just stays NULL, no errors
Future-proofs for audit expansion (add updated_by later without ORM changes)
Safer than mixing both mixins across models (consistency > optimization)

One-liner: Use AuditMixin universally unless table has deleted_at only (then add SoftDeleteMixin too).
 **

15. ** Never use str(e), (e) etc and other methods that can expose or leak internal 
logic or data upon returning public facing error reports

16. ** Tests must never reference uppercase enum members after normalization.
Only enum values are stable.
---

# **2. Database-Side Specification (Schema, Constraints, RLS, Migrations)**

## **2.1 Column & Type Rules**

* PKs:

  * BIGINT: `GENERATED ALWAYS AS IDENTITY`
  * UUID: `DEFAULT gen\_random\_uuid()`
* Timestamps:

  * `created\_at timestamptz DEFAULT now()`
  * `updated\_at timestamptz DEFAULT now()`
  * Optional: `deleted\_at timestamptz`
* ENUM Types:

  * Explicit `CREATE TYPE name AS ENUM (...)` in `public`.
* Numeric types:

  * Use `numeric(precision, scale)` for money/surface area (e.g., `numeric(12,2)`).
* Geo:

  * `geography(POINT, 4326)` or `geometry(Point, 4326)`.

## **2.2 Constraints & Indexes**

* CHECK constraints for:

  * lowercase email, rating ranges, non-negative values, etc.
* Indexes:

  * All FK columns.
  * Common filters.
  * `geom` via GiST.
  * Partial indexes for soft-deleted (`WHERE deleted\_at IS NULL`).

## **2.3 RLS & Authentication**

* Policies reference `auth.uid()` / `jwt.claims\['sub']` → local `supabase\_id UUID`.
* Policies expressed minimally using DB columns (`owner\_id`, `agency\_id`, `is\_admin`).

## **2.4 Migration Rules**

* All types (ENUM, PKs, FKs) created/altered explicitly in Alembic.
* Alembic env settings:

  * `include\_schemas=True`
  * `compare\_type=True`
  * `compare\_server\_default=True`
* CI:

  * `alembic revision --autogenerate` dry-run diff check.
  * `alembic upgrade --sql` must match expectations.

---

# **3. ORM / Python Specification**

## **3.1 Base & Metadata**

* One global `Base` with unified `metadata = MetaData(naming\_convention=...)`.
* Mixins:

  * `TimestampMixin` (created_at, updated_at)
  * `SoftDeleteMixin` (deleted_at)
  * `AuditMixin` (updated_by)
* Mixins must **not** override values unless DB diverges by design.

## **3.2 Column Rules**

* PKs:

  * `Column(BigInteger, primary\_key=True, Identity(always=True))`
  * or UUID column matching DB.
* Timestamps:

  * `DateTime(timezone=True), server\_default=func.now(), nullable=False`.
* FKs:

  * Type = referenced PK type; e.g., `Column(BigInteger, ForeignKey("users.id"))`.
* ENUMs:

  * `ENUM(..., name="enum\_name", create\_type=False)` matching DB.
* JSONB:

  * `Column(JSONB, nullable=False)` for search/filter payloads.
* Geo:

  * `Column(Geography(geometry\_type='POINT', srid=4326))`.

## **3.3 Relationships**

* Use explicit `back\_populates`.
* Avoid global eager loading; use per-query `selectinload`.
* `uselist=False` only for true one-to-one DB constraints.

## **3.4 ORM Hygiene**

* No `create\_all()`.
* Consistent imports (`BigInteger` vs `Integer`).
* Async or sync uniformly — never mixed arbitrarily.

---

# **4. Verification Checklist (Pass/Fail Gate for Every Table)**

For each table:

1. PK type correct (BIGINT/UUID)?
2. PK identity/default matches canonical spec?
3. “All creation/update timestamps = TIMESTAMPTZ DEFAULT now()
    Soft-delete timestamps = TIMESTAMPTZ DEFAULT NULL and set only on delete.”
4. ORM timestamps = timezone-aware + `server\_default=func.now()`?
5. FK type parity?
6. ENUM names/values matched with `create\_type=False`?
7. Geo = `Geography(POINT, 4326)`?
8. Numeric fields correct precision/scale?
9. Naming convention in effect?
10. No `create\_all()` usage?
11. Migrations reflect enum/FK/default changes properly?
12. RLS policies reference `supabase\_id` + tested?
13. Indexes exist for FKs/common filters/geom/partials?
14. No deprecated or mismatched imports/API usage?
15. ** Never use str(e), (e) etc and other methods that can expose or leak internal 
logic or data upon returning public facing error reports

If any fail → remediation required.

---

# **5. Remediation Procedure (Deterministic Fix Path)**

## **5.1 Table Creation Flow**

1. Create ORM model stub with canonical mixins/types.
2. Create matching Pydantic schemas (Base/Create/Update).
3. Add CRUD operations.
4. Add router endpoint.
5. Run tests.
6. `alembic revision --autogenerate`.
7. Manually inspect for ENUM/DEFAULT/FK correctness.
8. Apply migration to staging.
9. Run verification checklist.

## **5.2 Fixing FK Type Mismatches**

1. Update ORM to proper type.
2. Alembic migration: `ALTER TABLE ... ALTER COLUMN ... TYPE bigint USING ...::bigint`.

## **5.3 ENUM Mismatches**

1. Replace `String` with `ENUM(..., create\_type=False)` in ORM.
2. If DB missing ENUM: add via migration.
3. Never drop/recreate enums in production without safe migration plan.

## **5.4 Timestamp Inconsistencies**

1. Fix ORM → timezone-aware + `server\_default=func.now()`.
2. “All creation/update timestamps = TIMESTAMPTZ DEFAULT now()
    Soft-delete timestamps = TIMESTAMPTZ DEFAULT NULL and set only on delete.”

---

# **6. Alembic & CI Operations**

* Alembic env must include:

  * `include\_schemas=True`
  * `compare\_type=True`
  * `compare\_server\_default=True`
* CI pipeline must run:

  * Autogen diff check (fail on unexpected).
  * SQL-only upgrade check.
  * Manual approval for type-level changes.

---

# **7. Optional Automation (Verifier Script)**

Recommended script should:

1. Inspect DB (pg_type, pg_enum, pg_constraint, geometry_columns).
2. Inspect ORM (`sqlalchemy.inspect`).
3. Produce JSON diff of: types, FKs, enums, timestamps, indexes, geo types.
4. Output pass/fail per checklist item.

---

# **8. Final Operational Notes**

* BIGINT for high-growth tables; UUID when IDs must be externally safe.
* Keep migrations backward-compatible.
* Keep AI integrations isolated (`services/ai/`).
* Logs small, structured, rotated.
* Always run the verification checklist before merging any DB-affecting change.





Skills.md
Skills, insights and instructions:


# .md - Test Coverage Implementation Guide

> **Essential rules and patterns for achieving 80%+ test coverage on FastAPI + SQLAlchemy projects**

---

## 🎯 Core Testing Principles

### **1. Coverage Strategy: Layered Testing**

Build test coverage incrementally across multiple test files:

```
v1: Comprehensive baseline (60-70% coverage)
v2: Edge cases & variations (+10-15%)
v3: Surgical targeting of missed lines (+10-15%)
v4: Final cleanup for 85%+
```

**Why:** Prevents massive unmaintainable test files, allows parallel development, easier debugging.

---

### **2. Fixture Architecture**

**ALWAYS centralize fixtures in `conftest.py`:**

```python
# ✅ CORRECT: Centralized fixtures
@pytest.fixture
def sample_property(db: Session, normal_user, location, property_type):
    """Reusable across all test files"""
    return property_crud.create(db, obj_in=PropertyCreate(...), user_id=normal_user.user_id)

# ❌ WRONG: Duplicating fixtures in each test file
# (Leads to inconsistent test data and maintenance nightmare)
```

**Essential Fixtures Pattern:**
```python
# Single entity
sample_property

# Multiple entities for filtering/search
multiple_properties  # 4-10 diverse records

# Related entities
property_type, location, user

# Variations
property_type_villa, location_lekki
```

---

### **3. Transaction Safety**

**CRITICAL: Use `flush()` not `commit()` in fixtures**

```python
# ✅ CORRECT: Changes persist in transaction, rollback works
@pytest.fixture
def normal_user(db: Session):
       db.flush()  # ← Persist in transaction
    
# ❌ WRONG: Commits break test isolation
@pytest.fixture
def normal_user(db: Session):
    db.commit()  # ← Data persists across tests, causes UniqueViolation
    ```

**Ensure `conftest.py` has transaction rollback:**
```python
@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()  # ← Cleans up after each test
    connection.close()
```

---

### **4. Input Sanitization (Prevent SQL Errors)**

**ALWAYS sanitize pagination inputs in CRUD methods:**

```python
def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100):
    # ✅ CORRECT: Prevents "OFFSET must not be negative" error
    skip = max(0, skip)
    limit = max(0, limit)
    
    query = select(Model).offset(skip).limit(limit)
    return db.execute(query).scalars().all()
```

**Test for negative inputs:**
```python
def test_get_multi_with_negative_skip(db, multiple_records):
    # Should handle gracefully, not crash
    results = crud.get_multi(db, skip=-1, limit=10)
    assert isinstance(results, list)
```

---

### **5. Geospatial Standards (PostGIS)**

**Use Geography(POINT, 4326) for lat/lon data:**

```python
# Model definition
from geoalchemy2 import Geography

class Property(Base):
    geom = Column(Geography(geometry_type='POINT', srid=4326))
```

**CRITICAL: WKT coordinate order is LONGITUDE, LATITUDE**

```python
# ✅ CORRECT
WKTElement('POINT(3.3792 6.5244)', srid=4326)  # lon, lat

# ❌ WRONG
WKTElement('POINT(6.5244 3.3792)', srid=4326)  # lat, lon - BACKWARDS!
```

**Distance units: ST_DWithin uses METERS for Geography**

```python
# ✅ CORRECT: Convert km to meters
radius_meters = radius_km * 1000
ST_DWithin(Property.geom, point, radius_meters)

# ❌ WRONG: Using km directly
ST_DWithin(Property.geom, point, radius_km)  # Returns wrong results
```

**Bounding box order:**
```python
# ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, srid)
envelope = ST_MakeEnvelope(3.2, 6.4, 3.5, 6.7, 4326)
```

---

### **6. Soft Delete Pattern**

**ALWAYS exclude soft-deleted records in queries:**

```python
# ✅ CORRECT
query = select(Property).where(Property.deleted_at.is_(None))

# ❌ WRONG: Returns deleted records
query = select(Property)
```

**Soft delete implementation:**
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

**Test soft delete exclusion:**
```python
def test_get_multi_excludes_deleted(db, sample_property):
    # Delete
    crud.soft_delete(db, property_id=sample_property.property_id)
    
    # Should not appear in results
    props = crud.get_multi(db, skip=0, limit=100)
    assert sample_property.property_id not in [p.property_id for p in props]
```

---

### **7. Bulk Operations (Performance)**

**Use `update().where().values()` for bulk changes:**

```python
# ✅ CORRECT: Single SQL command
def bulk_verify(self, db: Session, *, property_ids: List[int]):
    stmt = (
        update(Property)
        .where(Property.property_id.in_(property_ids))
        .values(is_verified=True, verification_date=func.now())
    )
    result = db.execute(stmt)
    db.flush()
    return result.rowcount  # Number of records updated

# ❌ WRONG: N+1 queries, slow
def bulk_verify(self, db: Session, *, property_ids: List[int]):
    for prop_id in property_ids:
        prop = db.get(Property, prop_id)
        prop.is_verified = True
        prop.verification_date = datetime.now()
    db.commit()
```

**Test bulk operations:**
```python
def test_bulk_update_status(db, multiple_properties):
    prop_ids = [p.property_id for p in multiple_properties[:3]]
    
    count = crud.bulk_update_status(
        db,
        property_ids=prop_ids,
        new_status=ListingStatus.sold
    )
    
    assert count == 3  # Verify rowcount
```

---

### **8. Filter Implementation**

**Support optional filters via dict parameter:**

```python
def get_multi(
    self,
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
):
    query = select(Property).where(Property.deleted_at.is_(None))
    
    if filters:
        # Check for None to allow falsy values like 0 or False
        if "min_price" in filters and filters["min_price"] is not None:
            query = query.where(Property.price >= filters["min_price"])
        
        if "bedrooms" in filters and filters["bedrooms"] is not None:
            query = query.where(Property.bedrooms == filters["bedrooms"])
        
        # Boolean filters
        if "is_verified" in filters and filters["is_verified"] is not None:
            query = query.where(Property.is_verified == filters["is_verified"])
    
    return db.execute(query.offset(skip).limit(limit)).scalars().all()
```

**Test all filter combinations:**
```python
def test_filter_combined(db, multiple_properties):
    filters = {
        "min_price": 30000000,
        "max_price": 100000000,
        "bedrooms": 3,
        "is_verified": True
    }
    
    props = crud.get_multi(db, skip=0, limit=10, filters=filters)
    assert all(30000000 <= p.price <= 100000000 for p in props)
    assert all(p.bedrooms == 3 for p in props)
```

---

### **9. Test Organization**

**Use test classes for logical grouping:**

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

**Naming convention:**
```
test_{operation}_{scenario}
test_create_property_minimal_fields
test_get_multi_with_filters
test_bulk_update_status_empty_list
```

---

### **10. Edge Cases Always Test**

**Mandatory edge case tests for every CRUD operation:**

```python
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

---

### **11. Modern Real Estate Features (Required)**

**Essential features for production real estate platforms:**

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

---

### **12. Coverage Measurement**

**Run tests with coverage reporting:**

```bash
# Single file
pytest tests/crud/test_properties.py --cov=app/crud/properties --cov-report=term-missing

# Multiple files with wildcard
pytest tests/crud/test_properties_v*.py --cov=app/crud/properties --cov-report=term-missing

# HTML report for detailed analysis
pytest tests/ --cov=app --cov-report=html
```

**Interpret missing lines:**
```
Missing: 44-63, 139-263
```
- Large ranges (100+ lines) = Complex filter logic
- Scattered lines = Edge cases, error handling
- Low line numbers = Imports, base class methods

**Target coverage per file type:**
- CRUD: 80-90%
- Models: 90-95%
- Schemas: 85-95%
- API Endpoints: 70-80% (harder due to auth dependencies)
- Utils: 90-95%

---

### **13. Common Pitfalls to Avoid**

❌ **Using `pytest.skip()` for unimplemented features**
✅ **Implement the feature or remove the test**

❌ **Committing in fixtures**
✅ **Use flush() for transaction safety**

❌ **Testing with live database**
✅ **Use transaction rollback pattern**

❌ **Latitude/Longitude order confusion**
✅ **Remember: WKT is POINT(lon, lat)**

❌ **Using km with PostGIS ST_DWithin**
✅ **Convert to meters: km * 1000**

❌ **Forgetting to exclude deleted_at**
✅ **Always filter: .where(Model.deleted_at.is_(None))**

❌ **Hardcoding test data**
✅ **Use parametrize and fixtures**

❌ **Not testing error paths**
✅ **Test invalid inputs, not found, permission denied**

---

### **14. Canonical Compliance Checklist**

✅ Geography(POINT, 4326) for all geospatial data  
✅ WKT format: POINT(longitude latitude)  
✅ Soft delete on all models (deleted_at, deleted_by)  
✅ Audit trails (created_by, updated_by with Supabase IDs)  
✅ UTC timezone for all timestamps  
✅ No `str(e)` error exposure to users  
✅ Input validation via Pydantic schemas  
✅ Transaction-based testing with rollback  
✅ Coverage target: 80% minimum, 90% ideal  

---

## 🚀 Quick Start Template

```python
# tests/crud/test_<model>.py

import pytest
from sqlalchemy.orm import Session
from app.crud.<model> import <model> as <model>_crud
from app.models.<model> import <Model>
from app.schemas.<model> import <Model>Create, <Model>Update

# Fixtures in conftest.py
# @pytest.fixture
# def sample_<model>(db, user, related_entity):
#     return <model>_crud.create(...)

class Test<Model>Create:
    def test_create_minimal(self, db, user):
        obj = <model>_crud.create(db, obj_in=<Model>Create(...), user_id=user.user_id)
        assert obj.<field> == expected
    
    def test_create_complete(self, db, user):
        # All optional fields
        pass
    
    def test_create_invalid_<field>(self, db, user):
        with pytest.raises(ValidationError):
            <Model>Create(<field>=-1)

class Test<Model>Read:
    def test_get_by_id(self, db, sample_<model>):
        obj = <model>_crud.get(db, <model>_id=sample_<model>.<model>_id)
        assert obj is not None
    
    def test_get_multi(self, db, multiple_<model>s):
        objs = <model>_crud.get_multi(db, skip=0, limit=10)
        assert len(objs) >= 4
    
    def test_get_multi_excludes_deleted(self, db, sample_<model>):
        <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        objs = <model>_crud.get_multi(db, skip=0, limit=100)
        assert sample_<model>.<model>_id not in [o.<model>_id for o in objs]

class Test<Model>Update:
    def test_update_basic(self, db, sample_<model>):
        updated = <model>_crud.update(
            db, 
            db_obj=sample_<model>, 
            obj_in=<Model>Update(<field>=new_value)
        )
        assert updated.<field> == new_value

class Test<Model>Delete:
    def test_soft_delete(self, db, sample_<model>):
        deleted = <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        assert deleted.deleted_at is not None
    
    def test_restore(self, db, sample_<model>):
        <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        restored = <model>_crud.restore(db, <model>_id=sample_<model>.<model>_id)
        assert restored.deleted_at is None
```

---
### **15. PostGIS Antipodal Edge Prevention**

**Never use exact world boundaries in bounding box queries:**
```python
# ❌ WRONG: Causes "Antipodal edge detected"
min_lon=-180.0, max_lon=180.0

# ✅ CORRECT: Slightly inside boundaries
min_lon=-179.9, max_lon=179.9
min_lat=-89.9, max_lat=89.9
```

**Implement boundary clamping in CRUD:**
```python
# Clamp to safe ranges
min_lat = max(-89.9, min(89.9, min_lat))
max_lat = max(-89.9, min(89.9, max_lat))
min_lon = max(-179.9, min(179.9, min_lon))
max_lon = max(-179.9, min(179.9, max_lon))
```

**Why:** PostGIS Geography type cannot handle boxes that wrap exactly 360° around the globe - it creates a mathematical singularity.



## 📊 Success Metrics

- ✅ No pytest.skip() for production features
- ✅ Edge cases covered (empty, invalid, boundary)
- ✅ Transaction safety verified (no commit() in fixtures)
- ✅ Modern features implemented (geospatial, bulk ops, filters)

**Project is successful when:**
- ✅ Overall coverage ≥ 80%
- ✅ CRUD files ≥ 85%
- ✅ Models ≥ 90%
- ✅ Utils ≥ 90%
- ✅ All canonical rules followed

---

**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Applies To:** FastAPI + SQLAlchemy + PostGIS + Pytest projects





Additional Context from the External Analyst:
I understand perfectly. Using the MECE (Mutually Exclusive, Collectively Exhaustive) and DRY (Don't Repeat Yourself) principles, I have scoured our session to identify the specific architectural breakthroughs and problem-solving patterns we established.

🛠️ Engineering Standards & Patterns Template
1. Database Prerequisite Initialization
We solved the "Missing Object" error by manually injecting PostGIS extensions and custom PostgreSQL Enums into the test conftest.py before the model creation phase. This ensures the environment is "primed" for models that use existing database types, preventing the common failure where SQLAlchemy tries to build tables on top of non-existent definitions.

2. Strict Enum Type Casting
We corrected DatatypeMismatch errors by ensuring that all server_default values in the model are explicitly cast to their custom Enum types using the ::enum_name syntax. This follows the PostgreSQL industry standard for strict typing and prevents runtime errors during schema synchronization between different environments.

3. Model-to-DB Fidelity Verification
We established a breakthrough by cross-referencing SQLAlchemy model definitions against the "Supabase Truth" using information_schema queries to identify mismatches in nullability and defaults. This ensures the application remains the "source of truth" while respecting existing production constraints, making deployments predictable and safer.

4. Hybrid Environment Configuration
We successfully isolated the local test environment from production by forcing a local PostgreSQL engine configuration while maintaining the same schema logic. This provides a sandbox for high-velocity development without risking production data integrity or incurring cloud latency during CI/CD cycles.

5. Automated Dependency Resolution
We resolved complex ImportError issues by identifying that pytest requires explicit imports of related models (like PropertyType and Location) in the test configuration to register them with the metadata. This pattern is essential for global database consistency, ensuring that foreign key relationships are correctly mapped and created during test setup.

🚀 Next Step
Would you like me to formalize these into a CONTRIBUTING.md or a CODING_STANDARDS.md file that you can commit to your repository to ensure any future developer follows these exact protocols?



📋 Core Learnings (Battle-Tested Standards)
1. PostgreSQL ENUM Case Mismatch
Problem: Python Enum uses ACTIVE, DB stores 'active', SQLAlchemy gets confused
Solution: func.lower(cast(Model.status, String)) == value.lower()
Standard: Always use case-insensitive comparison for ENUM filters
2. SQLAlchemy 2.0 Query Immutability
Problem: query.where() doesn't modify original, returns new object
Solution: Always reassign: query = query.where(...)
Standard: Never orphan query modifications
3. Identity Map Cache Poisoning
Problem: Tests read from session cache, not actual DB
Solution: db.flush() then db.expire_all() before assertions
Standard: The "Double-Tap" for test isolation
4. Enum Type Registration with values_callable
Problem: SQLAlchemy doesn't know whether to use .name or .value
Solution: Always define: Enum(EnumClass, name="...", values_callable=lambda x: [e.value for e in x])
Standard: Explicit value mapping prevents type confusion




NEXT ACTUAL WORK
When you need to make your first real schema change:

# Example: Add bio field to User model
# 1. Edit app/models/users.py:
bio = Column(Text, nullable=True)

# 2. Generate migration:
alembic revision --autogenerate -m "add_user_bio_field"

# 3. Review the file
# 4. Apply it:
alembic upgrade head

# 5. Done! ✅





**also note, very important: for any interaction where weve solved a problem, but note only where we've successfully solved the problem determined by i share the results and you see the problem solved by which time you call my attention to it and we immediately add it as a skill or .md markdown for our skills or markdown document. thanks**



for any interaction where weve solved a problem, but note only where we've successfully solved the problem determined by i share the results and you see the problem solved by which time you call my attention to it and we immediately add it as a skill or .md markdown for our skills or markdown document. thanks



Testing Strategy

Fixture Reuse: Centralized in conftest.py for consistency
Transaction Isolation: flush() not commit() in fixtures
Skip vs Implement: Implemented all modern real estate features (no skips)

Code Architecture Decisions

Geospatial: PostGIS Geography(POINT, 4326) with meters
Bulk Operations: update().where().values() for performance
Input Sanitization: skip = max(0, skip) prevents SQL errors
Soft Delete: All queries exclude deleted_at IS NOT NULL
Audit Trails: updated_by_supabase_id tracking in bulk ops

Canonical Compliance
✅ All code follows Phase-2 Preflight spec:

Geography(POINT, 4326) for spatial data
WKT format: POINT(longitude latitude)
Soft delete patterns maintained
No str(e) error exposure
Proper timezone handling (UTC)


# .md - Test Coverage Implementation Guide

> **Essential rules and patterns for achieving 80%+ test coverage on FastAPI + SQLAlchemy projects**

---

## 🎯 Core Testing Principles

### **1. Coverage Strategy: Layered Testing**

Build test coverage incrementally across multiple test files:

```
v1: Comprehensive baseline (60-70% coverage)
v2: Edge cases & variations (+10-15%)
v3: Surgical targeting of missed lines (+10-15%)
v4: Final cleanup for 85%+
```

**Why:** Prevents massive unmaintainable test files, allows parallel development, easier debugging.

---

### **2. Fixture Architecture**

**ALWAYS centralize fixtures in `conftest.py`:**

```python
# ✅ CORRECT: Centralized fixtures
@pytest.fixture
def sample_property(db: Session, normal_user, location, property_type):
    """Reusable across all test files"""
    return property_crud.create(db, obj_in=PropertyCreate(...), user_id=normal_user.user_id)

# ❌ WRONG: Duplicating fixtures in each test file
# (Leads to inconsistent test data and maintenance nightmare)
```

**Essential Fixtures Pattern:**
```python
# Single entity
sample_property

# Multiple entities for filtering/search
multiple_properties  # 4-10 diverse records

# Related entities
property_type, location, user

# Variations
property_type_villa, location_lekki
```

---

### **3. Transaction Safety**

**CRITICAL: Use `flush()` not `commit()` in fixtures**

```python
# ✅ CORRECT: Changes persist in transaction, rollback works
@pytest.fixture
def normal_user(db: Session):
       db.flush()  # ← Persist in transaction
    
# ❌ WRONG: Commits break test isolation
@pytest.fixture
def normal_user(db: Session):
    db.commit()  # ← Data persists across tests, causes UniqueViolation
    ```

**Ensure `conftest.py` has transaction rollback:**
```python
@pytest.fixture(scope="function")
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()  # ← Cleans up after each test
    connection.close()
```

---

### **4. Input Sanitization (Prevent SQL Errors)**

**ALWAYS sanitize pagination inputs in CRUD methods:**

```python
def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100):
    # ✅ CORRECT: Prevents "OFFSET must not be negative" error
    skip = max(0, skip)
    limit = max(0, limit)
    
    query = select(Model).offset(skip).limit(limit)
    return db.execute(query).scalars().all()
```

**Test for negative inputs:**
```python
def test_get_multi_with_negative_skip(db, multiple_records):
    # Should handle gracefully, not crash
    results = crud.get_multi(db, skip=-1, limit=10)
    assert isinstance(results, list)
```

---

### **5. Geospatial Standards (PostGIS)**

**Use Geography(POINT, 4326) for lat/lon data:**

```python
# Model definition
from geoalchemy2 import Geography

class Property(Base):
    geom = Column(Geography(geometry_type='POINT', srid=4326))
```

**CRITICAL: WKT coordinate order is LONGITUDE, LATITUDE**

```python
# ✅ CORRECT
WKTElement('POINT(3.3792 6.5244)', srid=4326)  # lon, lat

# ❌ WRONG
WKTElement('POINT(6.5244 3.3792)', srid=4326)  # lat, lon - BACKWARDS!
```

**Distance units: ST_DWithin uses METERS for Geography**

```python
# ✅ CORRECT: Convert km to meters
radius_meters = radius_km * 1000
ST_DWithin(Property.geom, point, radius_meters)

# ❌ WRONG: Using km directly
ST_DWithin(Property.geom, point, radius_km)  # Returns wrong results
```

**Bounding box order:**
```python
# ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, srid)
envelope = ST_MakeEnvelope(3.2, 6.4, 3.5, 6.7, 4326)
```

---

### **6. Soft Delete Pattern**

**ALWAYS exclude soft-deleted records in queries:**

```python
# ✅ CORRECT
query = select(Property).where(Property.deleted_at.is_(None))

# ❌ WRONG: Returns deleted records
query = select(Property)
```

**Soft delete implementation:**
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

**Test soft delete exclusion:**
```python
def test_get_multi_excludes_deleted(db, sample_property):
    # Delete
    crud.soft_delete(db, property_id=sample_property.property_id)
    
    # Should not appear in results
    props = crud.get_multi(db, skip=0, limit=100)
    assert sample_property.property_id not in [p.property_id for p in props]
```

---

### **7. Bulk Operations (Performance)**

**Use `update().where().values()` for bulk changes:**

```python
# ✅ CORRECT: Single SQL command
def bulk_verify(self, db: Session, *, property_ids: List[int]):
    stmt = (
        update(Property)
        .where(Property.property_id.in_(property_ids))
        .values(is_verified=True, verification_date=func.now())
    )
    result = db.execute(stmt)
    db.flush()
    return result.rowcount  # Number of records updated

# ❌ WRONG: N+1 queries, slow
def bulk_verify(self, db: Session, *, property_ids: List[int]):
    for prop_id in property_ids:
        prop = db.get(Property, prop_id)
        prop.is_verified = True
        prop.verification_date = datetime.now()
    db.commit()
```

**Test bulk operations:**
```python
def test_bulk_update_status(db, multiple_properties):
    prop_ids = [p.property_id for p in multiple_properties[:3]]
    
    count = crud.bulk_update_status(
        db,
        property_ids=prop_ids,
        new_status=ListingStatus.sold
    )
    
    assert count == 3  # Verify rowcount
```

---

### **8. Filter Implementation**

**Support optional filters via dict parameter:**

```python
def get_multi(
    self,
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
):
    query = select(Property).where(Property.deleted_at.is_(None))
    
    if filters:
        # Check for None to allow falsy values like 0 or False
        if "min_price" in filters and filters["min_price"] is not None:
            query = query.where(Property.price >= filters["min_price"])
        
        if "bedrooms" in filters and filters["bedrooms"] is not None:
            query = query.where(Property.bedrooms == filters["bedrooms"])
        
        # Boolean filters
        if "is_verified" in filters and filters["is_verified"] is not None:
            query = query.where(Property.is_verified == filters["is_verified"])
    
    return db.execute(query.offset(skip).limit(limit)).scalars().all()
```

**Test all filter combinations:**
```python
def test_filter_combined(db, multiple_properties):
    filters = {
        "min_price": 30000000,
        "max_price": 100000000,
        "bedrooms": 3,
        "is_verified": True
    }
    
    props = crud.get_multi(db, skip=0, limit=10, filters=filters)
    assert all(30000000 <= p.price <= 100000000 for p in props)
    assert all(p.bedrooms == 3 for p in props)
```

---

### **9. Test Organization**

**Use test classes for logical grouping:**

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

**Naming convention:**
```
test_{operation}_{scenario}
test_create_property_minimal_fields
test_get_multi_with_filters
test_bulk_update_status_empty_list
```

---

### **10. Edge Cases Always Test**

**Mandatory edge case tests for every CRUD operation:**

```python
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

---

### **11. Modern Real Estate Features (Required)**

**Essential features for production real estate platforms:**

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

---

### **12. Coverage Measurement**

**Run tests with coverage reporting:**

```bash
# Single file
pytest tests/crud/test_properties.py --cov=app/crud/properties --cov-report=term-missing

# Multiple files with wildcard
pytest tests/crud/test_properties_v*.py --cov=app/crud/properties --cov-report=term-missing

# HTML report for detailed analysis
pytest tests/ --cov=app --cov-report=html
```

**Interpret missing lines:**
```
Missing: 44-63, 139-263
```
- Large ranges (100+ lines) = Complex filter logic
- Scattered lines = Edge cases, error handling
- Low line numbers = Imports, base class methods

**Target coverage per file type:**
- CRUD: 80-90%
- Models: 90-95%
- Schemas: 85-95%
- API Endpoints: 70-80% (harder due to auth dependencies)
- Utils: 90-95%

---

### **13. Common Pitfalls to Avoid**

❌ **Using `pytest.skip()` for unimplemented features**
✅ **Implement the feature or remove the test**

❌ **Committing in fixtures**
✅ **Use flush() for transaction safety**

❌ **Testing with live database**
✅ **Use transaction rollback pattern**

❌ **Latitude/Longitude order confusion**
✅ **Remember: WKT is POINT(lon, lat)**

❌ **Using km with PostGIS ST_DWithin**
✅ **Convert to meters: km * 1000**

❌ **Forgetting to exclude deleted_at**
✅ **Always filter: .where(Model.deleted_at.is_(None))**

❌ **Hardcoding test data**
✅ **Use parametrize and fixtures**

❌ **Not testing error paths**
✅ **Test invalid inputs, not found, permission denied**

---

### **14. Canonical Compliance Checklist**

✅ Geography(POINT, 4326) for all geospatial data  
✅ WKT format: POINT(longitude latitude)  
✅ Soft delete on all models (deleted_at, deleted_by)  
✅ Audit trails (created_by, updated_by with Supabase IDs)  
✅ UTC timezone for all timestamps  
✅ No `str(e)` error exposure to users  
✅ Input validation via Pydantic schemas  
✅ Transaction-based testing with rollback  
✅ Coverage target: 80% minimum, 90% ideal  

---

## 🚀 Quick Start Template

```python
# tests/crud/test_<model>.py

import pytest
from sqlalchemy.orm import Session
from app.crud.<model> import <model> as <model>_crud
from app.models.<model> import <Model>
from app.schemas.<model> import <Model>Create, <Model>Update

# Fixtures in conftest.py
# @pytest.fixture
# def sample_<model>(db, user, related_entity):
#     return <model>_crud.create(...)

class Test<Model>Create:
    def test_create_minimal(self, db, user):
        obj = <model>_crud.create(db, obj_in=<Model>Create(...), user_id=user.user_id)
        assert obj.<field> == expected
    
    def test_create_complete(self, db, user):
        # All optional fields
        pass
    
    def test_create_invalid_<field>(self, db, user):
        with pytest.raises(ValidationError):
            <Model>Create(<field>=-1)

class Test<Model>Read:
    def test_get_by_id(self, db, sample_<model>):
        obj = <model>_crud.get(db, <model>_id=sample_<model>.<model>_id)
        assert obj is not None
    
    def test_get_multi(self, db, multiple_<model>s):
        objs = <model>_crud.get_multi(db, skip=0, limit=10)
        assert len(objs) >= 4
    
    def test_get_multi_excludes_deleted(self, db, sample_<model>):
        <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        objs = <model>_crud.get_multi(db, skip=0, limit=100)
        assert sample_<model>.<model>_id not in [o.<model>_id for o in objs]

class Test<Model>Update:
    def test_update_basic(self, db, sample_<model>):
        updated = <model>_crud.update(
            db, 
            db_obj=sample_<model>, 
            obj_in=<Model>Update(<field>=new_value)
        )
        assert updated.<field> == new_value

class Test<Model>Delete:
    def test_soft_delete(self, db, sample_<model>):
        deleted = <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        assert deleted.deleted_at is not None
    
    def test_restore(self, db, sample_<model>):
        <model>_crud.soft_delete(db, <model>_id=sample_<model>.<model>_id)
        restored = <model>_crud.restore(db, <model>_id=sample_<model>.<model>_id)
        assert restored.deleted_at is None
```

---
### **15. PostGIS Antipodal Edge Prevention**

**Never use exact world boundaries in bounding box queries:**
```python
# ❌ WRONG: Causes "Antipodal edge detected"
min_lon=-180.0, max_lon=180.0

# ✅ CORRECT: Slightly inside boundaries
min_lon=-179.9, max_lon=179.9
min_lat=-89.9, max_lat=89.9
```

**Implement boundary clamping in CRUD:**
```python
# Clamp to safe ranges
min_lat = max(-89.9, min(89.9, min_lat))
max_lat = max(-89.9, min(89.9, max_lat))
min_lon = max(-179.9, min(179.9, min_lon))
max_lon = max(-179.9, min(179.9, max_lon))
```

**Why:** PostGIS Geography type cannot handle boxes that wrap exactly 360° around the globe - it creates a mathematical singularity.



## 📊 Success Metrics

**Session is successful when:**
- ✅ File coverage increases by 30%+ points
- ✅ All tests pass (0 failures)
- ✅ No pytest.skip() for production features
- ✅ Edge cases covered (empty, invalid, boundary)
- ✅ Transaction safety verified (no commit() in fixtures)
- ✅ Modern features implemented (geospatial, bulk ops, filters)

**Project is successful when:**
- ✅ Overall coverage ≥ 80%
- ✅ CRUD files ≥ 85%
- ✅ Models ≥ 90%
- ✅ Utils ≥ 90%
- ✅ All canonical rules followed

---

**Version:** 1.0  
**Last Updated:** 2026-02-06  
**Applies To:** FastAPI + SQLAlchemy + PostGIS + Pytest projects





Additional Context from the External Analyst:
I understand perfectly. Using the MECE (Mutually Exclusive, Collectively Exhaustive) and DRY (Don't Repeat Yourself) principles, I have scoured our session to identify the specific architectural breakthroughs and problem-solving patterns we established.

🛠️ Engineering Standards & Patterns Template
1. Database Prerequisite Initialization
We solved the "Missing Object" error by manually injecting PostGIS extensions and custom PostgreSQL Enums into the test conftest.py before the model creation phase. This ensures the environment is "primed" for models that use existing database types, preventing the common failure where SQLAlchemy tries to build tables on top of non-existent definitions.

2. Strict Enum Type Casting
We corrected DatatypeMismatch errors by ensuring that all server_default values in the model are explicitly cast to their custom Enum types using the ::enum_name syntax. This follows the PostgreSQL industry standard for strict typing and prevents runtime errors during schema synchronization between different environments.

3. Model-to-DB Fidelity Verification
We established a breakthrough by cross-referencing SQLAlchemy model definitions against the "Supabase Truth" using information_schema queries to identify mismatches in nullability and defaults. This ensures the application remains the "source of truth" while respecting existing production constraints, making deployments predictable and safer.

4. Hybrid Environment Configuration
We successfully isolated the local test environment from production by forcing a local PostgreSQL engine configuration while maintaining the same schema logic. This provides a sandbox for high-velocity development without risking production data integrity or incurring cloud latency during CI/CD cycles.

5. Automated Dependency Resolution
We resolved complex ImportError issues by identifying that pytest requires explicit imports of related models (like PropertyType and Location) in the test configuration to register them with the metadata. This pattern is essential for global database consistency, ensuring that foreign key relationships are correctly mapped and created during test setup.

🚀 Next Step
Would you like me to formalize these into a CONTRIBUTING.md or a CODING_STANDARDS.md file that you can commit to your repository to ensure any future developer follows these exact protocols?





🛠 Project RealtorNet: Engineering Standards & Reusable Skills
1. Granular Coverage Targeting (Surgical Testing)
We implemented "Surgical Testing" by using the --cov flag on specific modules rather than the whole project to isolate logic gaps.
Justification: This approach prevents "coverage dilution" where high-performing modules mask untested ones, ensuring that mission-critical CRUD logic reaches the 80% threshold independently of peripheral scripts.

2. Mock-Free Database Integration (SQLAlchemy Fixtures)
We solved database state issues by utilizing actual SQLAlchemy sessions within fixtures to test complex geospatial and relationship queries.
Justification: Testing against a real (test) database schema ensures that constraint violations and relationship lazy-loading issues are caught in CI, which is a global industry standard for high-reliability Fintech and Proptech apps.

3. Namespace & Collection Error Resolution
We resolved recursive ImportErrors by centralizing helper functions like get_auth_headers within tests/utils/__init__.py.
Justification: Exposing utilities through package entry points (dunder-init) prevents "stale" imports and collection crashes, a critical skill for maintaining large-scale Python monorepos where test discovery often fails.

4. Dynamic Slug & Collision Logic Validation
We developed a test suite that forces unique constraints by using uuid suffixes to validate agency and location "get-or-create" branches.
Justification: Validating slug-generation ensures URL stability and SEO integrity, providing a reusable template for any system requiring human-readable unique identifiers (slugs).

5. Deterministic Geospatial Benchmarking
We identified that "non-deterministic" coverage results were actually artifacts of early process interruptions during the test collection phase.
Justification: Differentiating between code execution errors and tracker failures is an essential debugging skill that prevents developers from wasting time refitting logic that isn't actually broken.

6. Environmental Path Forcing
We used PYTHONPATH="." to force the interpreter to prioritize the local source tree over stale virtual environment caches.
Justification: This technique is a vital "escape hatch" for Windows-based development environments where shell-specific pathing often obscures new file additions during the test discovery phase.




Standard,Implementation Rule
Testing Strategy,Use Surgical Tests for new features; move to Comprehensive Suites only after hitting >80% coverage.
DRY Imports,"All test helpers must be exposed via tests/utils/__init__.py to avoid ""deep-path"" import fragility."
MECE Coverage,Run coverage reports using explicit --cov=app.module flags to ensure no logic branch is ignored by accident.
Conflict Handling,Use --ignore flags during collection if peripheral API errors block the validation of core CRUD logic.




Audit Trail:
| table_name     | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| -------------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- |
| agencies       | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| agent_profiles | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| favorites      | created_at | n/a        | updated_at | n/a        | deleted_at | deleted_by |
| inquiries      | created_at | n/a        | updated_at | n/a        | deleted_at | deleted_by |
| locations      | created_at | n/a        | updated_at | updated_by | deleted_at | deleted_by |
| profiles       | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| properties     | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
| reviews        | created_at | n/a        | updated_at | n/a        | deleted_at | deleted_by |
| saved_searches | created_at | n/a        | updated_at | n/a        | deleted_at | deleted_by |
| users          | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |

