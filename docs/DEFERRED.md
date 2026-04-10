# Deferred Items

## DEF-007: psycopg3 prepared statement corruption in dev

Pattern: `DuplicatePreparedStatement`, `ProtocolViolation`, and `InFailedSqlTransaction` errors appearing after extended backend uptime or connection disruption.

Resolved by restarting Uvicorn.

Pre-launch: investigate `prepared_statement_cache_size=0` on the psycopg3 connection string or switch to `NullPool` for the dev engine to prevent statement caching across requests.

## DEF-008: Amenities checkbox grid not rendering in AmenitySelector

Component mounts correctly, `propertyId` prop is valid, both `/api/v1/amenities/` and `/api/v1/property-amenities/property/{id}` return `200`. Component reaches the render path but checkboxes do not appear visually.

Suspected cause: data shape mismatch between `AmenityResponse` from the catalogue endpoint and the `toAmenityOption` normalizer, or `AmenityCheckboxGrid` receiving correct data but rendering off-screen or with zero height.

Debug in Phase E with React DevTools to inspect component tree and prop values directly.
