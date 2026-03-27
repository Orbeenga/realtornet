Scaffold or extend a backend feature for: $ARGUMENTS

Project rules:
- Follow existing RealtorNet structure:
  app/models
  app/schemas
  app/crud
  app/api/endpoints
- Database is the source of truth
- Match FK type parity exactly
- Use BIGINT identities where the DB uses them
- Use DateTime(timezone=True) for timestamptz columns
- Use explicit Postgres enums where already established
- Avoid phantom fields and avoid backend-only drift

Workflow:
1. Inspect existing adjacent modules for exact local conventions
2. Mirror the established pattern across model, schema, crud, and router
3. Keep changes lean and dependency-ordered
4. Do not introduce create_all or schema-guessing behavior
5. Summarize files created/updated and any assumptions made
