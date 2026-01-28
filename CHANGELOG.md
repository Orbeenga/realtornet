# Changelog

All notable changes to the RealtorNet project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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