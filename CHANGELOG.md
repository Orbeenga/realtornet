# Changelog

All notable changes to the RealtorNet project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.5.2] - 2026-04-10

### Added
- Amenities catalogue seeded with 15 residential property amenities for Phase D backend support
- Deferred tracker refreshed: DEF-006 and DEF-007 logged, DEF-008 marked resolved

### Changed
- `docs/DEFERRED.md`: aligned deferred-item state with completed Phase D backend work

### Fixed
- `app/services/storage_services.py`: all storage uploads and deletes now use `get_supabase_admin_client()` for write-capable Supabase Storage access
- `app/services/storage_services.py`: uploads now derive and send explicit MIME type metadata, with `image/jpeg` fallback for unsupported guesses
- `app/services/storage_services.py`: removed dict-style `UploadResponse` error inspection and now rely on SDK exception flow for upload failures
- `app/services/storage_services.py`: upload `upsert` option now uses string `"true"` instead of Python `True` to satisfy the current storage/http client expectations
- `app/services/storage_services.py`: `delete_file()` now uses the same admin client path as uploads for consistent storage permissions
- `app/services/storage_services.py`: expanded storage error logging to include `error_type` and `error_message` before returning safe client-facing errors

## [0.5.1] - 2026-03-31

### Added
- Type-safety hardening pass (`v0.5.1`): project-wide pyright reduced from 388 to 0 errors and `pyrightconfig.json` added at basic enforcement level

### Changed
- Database ops note: `update_updated_at_column` search_path hardening (`SET search_path = public`) was applied directly in Supabase dashboard and is tracked as an external DB operation (not currently Alembic-managed in this repo).
- `endpoints/profiles.py`: aligned endpoint field usage from `profile_picture_url` to canonical `profile_picture`

### Fixed
- `crud/saved_searches.py`: implemented missing `execute_search()` so saved-search execution now applies stored JSON filters against properties
- Type-hardening surfaced and resolved two latent integration gaps during the 388 -> 0 pyright pass
- `crud/users.py`: Replaced `db.commit()` with `db.flush()` throughout - eliminates test isolation violations
- `crud/users.py`: `get()` now excludes soft-deleted users
- `crud/users.py`: `activate()` now correctly fetches deleted users for restore; preserves `deleted_by` audit history on restore
- `crud/users.py`: `deactivate()` and `soft_delete()` now always set `deleted_by` atomically with `deleted_at` (CLAUDE.md §1.3)
- `crud/users.py`: `get_agents()` and `search()` now exclude soft-deleted users
- `crud/properties.py`: `get()` now excludes soft-deleted properties
- `crud/properties.py`: `restore()` now correctly fetches deleted properties; preserves `deleted_by` audit history on restore
- `crud/properties.py`: Bulk operations no longer manually set `updated_at` (DB trigger is authoritative per CLAUDE.md §1.4)
- `endpoints/admin.py`: Corrected activate/deactivate docstrings to accurately describe soft-delete/restore semantics

### Removed
- `app/core/dependencies.py`: Dead shim - no imports existed outside the file itself

## [0.5.0] - 2026-03-16

### Added
- Complete audit trail implementation across all 10 entities with created_by, updated_by, deleted_by, deleted_at correctly populated in CRUD and exposed in Response schemas
- soft_delete() method to LocationCRUD; get_by_user_id() to ProfileCRUD
- count_by_agency(), count_by_user() to PropertyCRUD
- count_by_agency() to UserCRUD
- count_active(), activate(), deactivate() to UserCRUD for admin operations
- count_active(), count_approved(), count_pending() to PropertyCRUD
- count_active() to InquiryCRUD
- Analytics views migration: active_properties, agent_performance
- CLAUDE.md — canonical architectural decisions and standing rules
- Preflight Rules.md — pre-implementation checklist
- Full HTTP-layer test suites for all endpoint and CRUD modules (63% → 91.34% coverage)

### Fixed
- soft_delete() across favorites, inquiries, reviews, properties, users was setting updated_by instead of deleted_by — audit corruption
- create() for properties and users was not setting created_by
- locations CRUD create() was incorrectly setting updated_by
- profiles endpoint was accessing profile_in.user_id (field doesn't exist on schema) and not passing user_id to CRUD
- Logger calls in agencies.py referencing Pydantic class instead of instance
- Agency deletion guard was counting AgentProfile records instead of users — agents without profiles could bypass the guard
- All _by schema fields changed from Optional[str] to Optional[UUID] to match ORM type
- saved_searches CRUD db_obj argument mismatch
- auth.py refresh endpoint user-not-found branch was being swallowed by broad except Exception

### Changed
- ProfileCreate schema no longer accepts user_id — derived from authenticated user in endpoint
- All Response schemas now expose full audit trail fields including deleted_at

## [0.4.0] - 2026-01-21

### Database Migration System
- **Established Alembic baseline migration** for existing Supabase schema
- **Fixed 22 ORM-DB mismatches** across 9 model files:
  - Corrected timestamp nullability (nullable=True for all timestamps)
  - Fixed boolean server defaults (text() wrapper for SQL expressions)
  - Renamed generic `id` columns to semantic names (profile_id, amenity_id)
  - Added missing columns (locations.is_active)
  - Fixed ENUM server defaults (inquiry_status)
- **Configured Alembic for Supabase/PostGIS**:
  - Custom `render_item()` for PostGIS Geography types
  - Enhanced `include_object()` to filter cosmetic differences
  - Handles legacy Supabase naming conventions (idx_*, *_fkey)
  - Prevents full schema introspection hangs
- **Decoupled from Supabase auth schema**:
  - Dropped all FK constraints to auth.users
  - Maintained internal public schema relationships (18 FKs)
  - Application-level auth validation via supabase_id UUID

### Models
- Fixed `base.py` mixins (TimestampMixin, AuditMixin, SoftDeleteMixin)
- Corrected column types across all models:
  - users.py: Boolean defaults aligned with DB
  - agent_profiles.py: license_number VARCHAR(50) → String(50)
  - inquiries.py: inquiry_status TEXT → ENUM with proper server_default
  - locations.py: Added is_active boolean column
  - profiles.py: Renamed id → profile_id (semantic naming)
  - amenities.py: Renamed id → amenity_id (semantic naming)
  - properties.py: Fixed 7 boolean server_default wrappers
  - agencies.py: Removed non-existent is_admin column
  - property_amenities.py: Fixed FK reference to amenities.amenity_id
  - analytics.py: Fixed view column types (Integer → BigInteger)

### Infrastructure
- Migration baseline stamped: `d1ba4e701ce3_baseline_existing_supabase_schema`
- Database is now Single Source of Truth (SSOT)
- Alembic autogenerate ready for future schema changes
- PostGIS geography columns properly handled

### Documentation
- Defined migration workflow (no longer use `alembic check`)
- Documented Supabase naming convention handling
- Added inline comments for all ORM-DB alignment decisions

### Breaking Changes
- None (baseline migration only marks existing state)

### Known Issues
- `alembic check` hangs on Supabase/PostGIS (expected behavior, use `revision --autogenerate` instead)

---

## [0.3.0] - 2026-01-09

### Database
- Complete DB ↔ ORM alignment (15 tables)
- Alembic migration system implemented
- PostgreSQL with PostGIS support
- Row Level Security (RLS) ready

### API Development
- Full CRUD operations for all entities
- JWT authentication with Supabase integration
- Multi-tenant support (agency-based)
- Soft delete implementation
- Request validation and error handling

### Testing
- Pytest configuration with 80% coverage requirement
- Test fixtures for users and database
- Authentication endpoint tests

### Services
- Email service (Mailgun integration)
- File storage (Supabase Storage)
- Analytics service with DB views
- Celery task queue for background jobs

### Security
- Rate limiting middleware (Redis-based)
- Password hashing (bcrypt, 12 rounds)
- Token refresh mechanism
- Audit trail (updated_by, deleted_by tracking)

### Performance
- Database connection pooling
- Redis caching infrastructure
- Optimized queries with proper indexing

---

## [0.2.0] - 2025-03-28

### Added 
- Comprehensive logging module with console and file logging
- Centralized error handling framework
- Custom exception classes
- Standardized error response mechanism

### Infrastructure
- Initial project structure setup
- GitHub repository preparation
- Virtual environment configuration

### Security
- Basic error logging and tracking
- Error response standardization
- Enhanced token management system
- Timezone-aware authentication
- Stricter token validation mechanisms

---

## [0.1.0] - 2025-03-27

### Added
- Comprehensive logging module with console and file logging
- Centralized error handling framework
- Custom exception classes
- Standardized error response mechanism

### Infrastructure
- Initial project structure setup
- GitHub repository preparation
- Virtual environment configuration

### Security
- Basic error logging and tracking
- Error response standardization

---

## Notes

### Migration History
- **v0.4.0**: Established Alembic baseline for existing Supabase schema (Batch 7)
- **v0.3.0**: Initial DB/ORM alignment (Batches 1-6)
- **v0.2.0**: Security enhancements
- **v0.1.0**: Project foundation

### Database Migration Workflow
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Review generated file
# app/db/migrations/versions/XXXX_description.py

# Apply migration
alembic upgrade head

# Verify
alembic current
```

### Supabase Schema Management
- Database tables managed via migrations (public schema)
- Auth system managed by Supabase (auth schema)
- Storage buckets managed by Supabase (storage schema)
- RLS policies to be applied in next release (v0.4.1)
