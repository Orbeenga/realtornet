# Deferred Items

## DEF-006: Supabase storage bucket provisioning and policy verification

Phase D fixed backend storage writes by switching all upload/delete operations to the admin client, but bucket existence, public exposure, and environment-side policy verification still live outside this repo.

Current expectation: `property-images`, `profile-images`, and `agency-logos` already exist in each target Supabase project before backend deploys.

Pre-launch: add deployment-time validation or provisioning automation so storage buckets and required access settings are checked explicitly per environment.

## DEF-007: psycopg3 prepared statement corruption in dev

Pattern: `DuplicatePreparedStatement`, `ProtocolViolation`, and `InFailedSqlTransaction` errors appearing after extended backend uptime or connection disruption.

Resolved by restarting Uvicorn.

Pre-launch: investigate `prepared_statement_cache_size=0` on the psycopg3 connection string or switch to `NullPool` for the dev engine to prevent statement caching across requests.

## DEF-008 (Resolved): Amenities checkbox grid not rendering in AmenitySelector

Phase D backend work removed the backend data blocker for the selector by ensuring the amenities catalogue is seeded with 15 items and the amenity payload shape is stable for consumers.

Resolved status: backend support is complete. Any future visual rendering-only regression should be tracked separately in the frontend workstream rather than kept open as a backend deferred item.
