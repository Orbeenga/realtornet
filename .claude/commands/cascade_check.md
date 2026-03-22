Run a cascade behavior check for: $ARGUMENTS

References:
- `CLAUDE.md`
- `PREFLIGHT.md`

Focus:
- Soft delete propagation (`deleted_at`) across related models.
- Guard conditions against authoritative sources (e.g., `users` is SSOT over `agent_profiles`).
- State transition guards (active, inactive, deleted) are consistent.
- Counts and listings exclude soft-deleted records.

Output:
- List cascade risks and missing guards.
- Provide concrete fixes with file paths.