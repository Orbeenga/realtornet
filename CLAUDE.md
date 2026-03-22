# RealtorNet — Canonical Rules & Architectural Decisions

This file is the authoritative reference for all architectural decisions, standing rules,
and hard-won lessons from the RealtorNet build and test campaign. Claude must consult this
file before making any recommendation that touches models, CRUD, schemas, endpoints, or tests.

Script lookup workflow:
- Read `scriptReferences.md` first when locating scripts or command files.
- Update `scriptReferences.md` immediately after adding, renaming, or refactoring any script.

---

## 1. Audit Trail Architecture

### 1.1 Audit Column Matrix (Canonical)

| table          | created_at | created_by | updated_at | updated_by | deleted_at | deleted_by |
|----------------|------------|------------|------------|------------|------------|------------|
| agencies       | ✓          | ✓ UUID     | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| agent_profiles | ✓          | ✓ UUID     | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| favorites      | ✓          | ✗          | ✓          | ✗          | ✓          | ✓ UUID     |
| inquiries      | ✓          | ✗          | ✓          | ✗          | ✓          | ✓ UUID     |
| locations      | ✓          | ✗          | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| profiles       | ✓          | ✓ UUID     | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| properties     | ✓          | ✓ UUID     | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| reviews        | ✓          | ✗          | ✓          | ✗          | ✓          | ✓ UUID     |
| saved_searches | ✓          | ✗          | ✓          | ✗          | ✓          | ✓ UUID     |
| users          | ✓          | ✓ UUID     | ✓          | ✓ UUID     | ✓          | ✓ UUID     |
| amenities      | ✗          | ✗          | ✗          | ✗          | ✗          | ✗          |

**amenities** is a reference/lookup table. No audit trail. No soft delete. This is intentional.

### 1.2 `_by` Column Rules

- All `_by` columns store `supabase_id` (UUID), not `user_id` (int).
- `_by` columns are **soft references only** — no FK constraint to `users.supabase_id`.
  This is a deliberate architectural decision to avoid cascade complexity on user deletion.
  Do not add FK constraints to `_by` columns.

### 1.3 CRUD Method Rules

**`create()`**
- Sets `created_by=supabase_id` where applicable (see matrix).
- Must NEVER set `updated_by` or `deleted_by`.
- For user self-registration: `created_by` = the new user's own `supabase_id` (self-referential).

**`update()`**
- Sets `updated_by=supabase_id` where applicable (see matrix).
- Must NEVER touch `created_by` or `deleted_by`.

**`soft_delete()`**
- Must ALWAYS set BOTH `deleted_at=func.now()` AND `deleted_by=supabase_id` together.
- Setting one without the other is an incomplete audit trail and a bug.
- Must NEVER set `updated_by` on delete — these are different audit events.

### 1.4 `updated_at` — DB Trigger Is the Authority

`updated_at` is managed exclusively by per-table DB triggers (`update_*_updated_at`).
The ORM mixin intentionally does NOT use `onupdate=func.now()`.

```python
# CORRECT — app/models/base.py TimestampMixin
class TimestampMixin:
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # NO onupdate= here — DB trigger handles it. Adding onupdate= is a bug.
```

If you see a recommendation to add `onupdate=func.now()` to the ORM mixin, reject it.
The DB already has both `update_*_updated_at` and `set_updated_at` triggers per table.
Adding ORM `onupdate` would cause double-firing.

### 1.5 Response Schema Rules

Every Response schema must expose all applicable audit fields from the matrix.
The `AgencyResponse` schema is the canonical reference implementation:

```python
class AgencyResponse(AgencyBase):
    agency_id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None   # where applicable per matrix
    updated_by: Optional[UUID] = None   # where applicable per matrix
    deleted_by: Optional[UUID] = None   # always for soft-delete entities

    model_config = ConfigDict(from_attributes=True)
```

**Rule:** `deleted_at` missing from a Response schema is always a bug.
Soft-delete is a business event and must be observable in the API response.

---

## 2. SQLAlchemy Rules

### 2.1 Query Style
Always use SQLAlchemy 2.0 `select()` style. Never use legacy `db.query()`.

```python
# CORRECT
stmt = select(func.count(Property.property_id)).where(...)
return db.execute(stmt).scalar()

# WRONG — legacy style, do not use
db.query(Property).filter(...).count()
```

### 2.2 Soft Delete Pattern
```python
def soft_delete(self, db: Session, *, obj_id: int, deleted_by_supabase_id: str):
    stmt = (
        update(ModelClass)
        .where(ModelClass.id == obj_id, ModelClass.deleted_at.is_(None))
        .values(deleted_at=func.now(), deleted_by=deleted_by_supabase_id)
    )
    db.execute(stmt)
    db.flush()
```

### 2.3 Bulk Soft Delete Pattern
Never loop + soft_delete for bulk operations. Use a single UPDATE...WHERE IN():

```python
def bulk_soft_delete(self, db, *, user_id, ids, deleted_by_supabase_id=None):
    stmt = (
        update(ModelClass)
        .where(ModelClass.user_id == user_id, ModelClass.id.in_(ids),
               ModelClass.deleted_at.is_(None))
        .values(deleted_at=func.now())
    )
    result = db.execute(stmt)
    db.flush()
    return result.rowcount
```

### 2.4 Joining Through Users for Agency Queries
`Property` has no `agency_id` column. Properties link to agencies through users.
Always join through `User` when querying properties by agency:

```python
stmt = (
    select(Property)
    .join(User, Property.user_id == User.user_id)
    .where(User.agency_id == agency_id, Property.deleted_at.is_(None))
)
```

### 2.5 Association Table Insert
```python
from app.models.property_amenities import property_amenities as pa_table
db.execute(pa_table.insert().values(property_id=..., amenity_id=...))
db.flush()
```

### 2.6 WKT Coordinate Order
Always POINT(longitude latitude) — longitude first.
ST_DWithin uses meters: `radius_km * 1000`.

---

## 3. FastAPI / Endpoint Rules

### 3.1 Query Parameter Naming
Never name a query parameter `status` — it shadows `from fastapi import status`.
Use descriptive names: `inquiry_status`, `listing_status`, etc.

### 3.2 DELETE Endpoints with Body
`TestClient.delete()` does not support `json=`.
Use `Query(...)` params for DELETE endpoints, not request body.

### 3.3 Audit Passthrough Pattern
Endpoints must pass `current_user.supabase_id` through to CRUD for all audit fields:

```python
# create
crud.create(db, obj_in=data, created_by=current_user.supabase_id)

# update
crud.update(db, db_obj=obj, obj_in=data, updated_by=current_user.supabase_id)

# soft_delete
crud.soft_delete(db, obj_id=obj_id, deleted_by_supabase_id=current_user.supabase_id)
```

Entities with no `created_by`/`updated_by` (favorites, inquiries, reviews, saved_searches)
must NOT pass those fields — they are not in the schema and will cause TypeError.

---

## 4. Schema Pattern Rules

### 4.1 Schema Hierarchy
All schemas follow: `Base → Create → Update → Response → ListResponse`

- `Base` — shared fields, validators
- `Create` — inherits Base, required fields explicit, no DB-generated fields
- `Update` — standalone (not from Base), all fields Optional
- `Response` — inherits Base, adds all DB-generated fields including full audit trail
- `ListResponse` — wraps `list[Response]` with pagination fields

### 4.2 Decimal Fields in Tests
Never use `PropertyCreate(...).model_dump()` directly in test JSON payloads.
Pydantic Decimal fields are not JSON serializable. Use plain int/float literals in test dicts.

---

## 5. Test Rules

### 5.1 Business Logic First
When a test reveals a logic gap, fix the logic. Never modify a test to hide a logic failure.
Tests are the canary. The business rule is the authority.

### 5.2 Logic Drift (from mabl research)
Green tests do not guarantee correct business logic.
Every test must assert the business rule, not just the HTTP status code.

In an agentic workflow, a passing test is a decision input to the system.
The bar for test correctness is higher than in manual review workflows.

### 5.2.1 Operational Rules (Audit Campaign)
- Logic drift is silent. Green tests do not mean correct business logic. Every test must assert the business rule, not just the HTTP status code.
- A passing test in an agentic workflow is a decision input, not a human signal. Tests must preserve intent, not just produce green.
- Every Response schema must expose deleted_at. Soft-delete is a business event â€” it must be observable in the API response.
- deleted_by must be set alongside deleted_at in every soft_delete operation. One without the other is incomplete audit trail.
- Guard conditions must be checked against the authoritative source. Agency deletion guard must count users by agency_id, not agent profiles â€” because an agent can exist without a profile.
- Fix logic, not tests. When a test reveals a logic gap, fix the logic. Tests are the canary, not the problem.
- Capture signal from failures. Every bug found is structured knowledge. Document it. The why-it-failed is the valuable part.

### 5.3 Guard Conditions Must Use the Authoritative Source
Check guard conditions against the real data source, not a proxy.

**Example — wrong:**
```python
# Counts agent profiles — misses agents without profiles
count = agent_profile_crud.count_by_agency(db, agency_id=agency_id)
```

**Example — correct:**
```python
# Counts users with agency_id — catches all agents regardless of profile status
count = user_crud.count_by_agency(db, agency_id=agency_id)
```

### 5.4 Fixture Rules
- Use `db.flush()` never `db.commit()` in fixtures.
- Every variable used in a test method must appear in its signature as a fixture parameter.
- `sample_property` is ALWAYS owned by `normal_user`. Never use it where `agent_token_headers`
  needs to be the property owner. Use `unverified_property_owned_by_agent` instead.

### 5.5 `generate_access_token` Signature
```python
token = generate_access_token(
    supabase_id=user.supabase_id,
    user_id=user.user_id,
    user_role=user.user_role.value,  # user_role= not role=
)
```

### 5.6 User Model Required Fields in Tests
When creating `User` objects directly in tests, these fields are NOT NULL:
`email`, `supabase_id`, `user_role`, `password_hash`, `first_name`, `last_name`

```python
User(
    email=f"test_{uuid.uuid4().hex[:6]}@example.com",
    supabase_id=str(uuid.uuid4()),
    user_role=UserRole.AGENT,
    password_hash="hashed_placeholder",
    first_name="Test",
    last_name="Agent",
)
```

### 5.7 No Direct-Call Final Coverage
Direct-call tests (bypassing the HTTP layer via direct function invocation) are not
acceptable as the final coverage solution for endpoint files. They may be used
temporarily during diagnosis but must be replaced with HTTP-layer tests once the
logic is correct. Coverage achieved via direct-call bypass is false coverage
and will be rejected.

### 5.8 user_id in Profiles Comes from Auth, Not Request Body
A user creates their own profile. user_id is always derived from current_user.user_id
in the endpoint, never from the request payload. ProfileCreate must not contain user_id.
This prevents a user from creating a profile on behalf of another user.

### 5.9 Inline Commentary Habit
Use inline comments and short docstrings liberally where they clarify decisions,
business rules, or non-obvious implementation details. The goal is explicit intent,
not boilerplate.

### 5.10 Targeted Test Runs Must Disable Coverage

Never run pytest on a subset of tests with coverage enabled.
The global `--cov-fail-under` threshold will fire against partial
coverage and produce a false failure.

```bash
# CORRECT — targeted run, no coverage measurement
pytest tests/api/endpoints/test_admin.py -v --no-cov

# CORRECT — full suite with coverage
pytest tests/ --cov=app --cov-report=term-missing

# WRONG — triggers global threshold on partial coverage
pytest tests/api/endpoints/test_admin.py -q
```

The `--no-cov` flag is mandatory on all targeted runs.
Coverage measurement is only valid on the full test suite.

---

## 6. Logging Rules

### 6.1 Logger Calls — Instance vs Class
Always log against the instance, never the class:

```python
# WRONG — AttributeError at runtime
logger.info("Created", extra={"id": AgencyResponse.agency_id})

# CORRECT
logger.info("Created", extra={"id": agency.agency_id})
```

### 6.2 Reserved `extra={}` Field Names
Never use these in `extra={}` — they shadow Python logging internals:
`filename`, `lineno`, `funcName`, `module`, `pathname`, `name`, `levelname`,
`levelno`, `created`, `thread`, `process`, `message`, `asctime`

Prefix custom keys: `image_filename`, `source_file`, etc.

---

## 6.3 Documentation and Commentary

Adopt a habit of liberal inline comments and concise docstrings across entity layers
(models, CRUD, schemas, endpoints) when it clarifies decisions, business rules, or
non-obvious implementation details. The goal is explicit architecture and intent,
not boilerplate. When a decision is non-standard or easy to misinterpret, comment it.

---

## 7. SQLAlchemy Table vs CRUD Name Collision

When a CRUD module imports a Table object with the same name as the module's singleton,
rename the Table import with a `_table` suffix. Add a backward-compat alias if needed:

```python
from app.models.property_amenities import property_amenities as pa_table
property_amenity = property_amenities  # backward compat alias
```

---

## 8. FK Constraint Policy

`_by` audit columns are soft UUID references. No FK to `users.supabase_id`.
This is a deliberate decision — FK constraints on audit columns cause cascade
complexity on user deletion and are not enforced at the DB level in this project.

If you see a recommendation to add FK constraints to `_by` columns, reject it
unless explicitly re-evaluated with the full cascade impact considered.

---

## 9. Inline Commenting Standard (Enforced Architecture)

### 9.1 Tool Hierarchy

Four commenting tools exist. Each has exactly one role:

1. **File header** - `# app/models/properties.py` - always the first line of every file.
2. **Section heading** - `# --- SECTION NAME ---` - block breaks in long files (CRUD, endpoints).
   Use sparingly in short files.
3. **Inline comment** - `# explanation` - the primary tool. Used beside a line, above a line,
   or below a line to explain decisions, constraints, and non-obvious logic.
4. **Docstring** - `"""..."""` - restricted. Only inside `def` blocks where IDE hover or
   Sphinx generation is the explicit goal. Never on class bodies. Never as a substitute
   for inline comments.

### 9.2 Prohibited Patterns

```python
# WRONG - docstring on class body
class Property(Base, AuditMixin, SoftDeleteMixin):
    """Property listing model."""

# CORRECT - inline comment on class body
class Property(Base, AuditMixin, SoftDeleteMixin):
    # Property listing model.
    # Primary Key: property_id (bigint GENERATED ALWAYS AS IDENTITY)

# WRONG - docstring substituting for inline decision comment
listing_status = Column(...)
"""Soft enum reference, create_type=False"""

# CORRECT - inline comment beside the line
listing_status = Column(...)  # soft enum ref, create_type=False - PREFLIGHT section 4

# WRONG - bland uncommented column block
property_id = Column(BigInteger, primary_key=True, autoincrement=True)
user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)

# CORRECT - each non-obvious line carries its reason
property_id = Column(BigInteger, primary_key=True, autoincrement=True)  # PK - bigint GENERATED ALWAYS AS IDENTITY
user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)  # FK - agency resolved through User, not direct
```

### 9.3 Long File Structure (CRUD and Endpoints)

Files over ~100 lines use section headings to break logical blocks:

```python
# app/crud/properties.py

# --- QUERY METHODS ---

# --- WRITE METHODS ---

# --- SOFT DELETE & RESTORE ---

# --- BULK OPERATIONS ---

# --- ADMIN METHODS ---
```

### 9.4 Enforcement Rule

If a `"""docstring"""` appears outside a `def` block, it is a violation.
If a column, relationship, or constraint has no inline comment explaining
a non-obvious decision, it is incomplete.
The analyst must apply the four-tool hierarchy on every file touched.

---

## 10. Coverage Campaign Status (as of 2026-03-10)

- **Coverage:** 81.88% — threshold 80% met
- **Tests:** 1368 passed, 1 skipped, 0 failed
- **Completed:** favorites (98%), inquiries (87%), reviews (98%), properties (98%),
  property_amenities (100%), property_types (100%), users (100%), favorites (98%),
  agencies (92%), agent_profiles (91%)
- **Remaining audit trail fixes:** See Batches 1–4 in session notes
- **Next campaign:** Business logic / guard condition correctness pass
