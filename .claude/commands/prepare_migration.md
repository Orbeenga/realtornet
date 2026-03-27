Prepare a safe Alembic migration plan for: $ARGUMENTS

Project rules:
- DB-first architecture
- Use naming conventions compatible with existing metadata
- Prefer additive/safe migration sequencing
- Add FKs after table creation when ordering risk exists
- Preserve production-safe assumptions
- No destructive change without clearly stating the risk

Workflow:
1. Identify the exact schema change requested
2. Check affected models/schemas/crud/routes
3. Draft the migration sequence in safe dependency order
4. Highlight data migration or backfill risk if any
5. Provide exact terminal commands and file targets
