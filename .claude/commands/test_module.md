Write or update pytest coverage for: $ARGUMENTS

Project context:
- FastAPI backend
- SQLAlchemy 2.x ORM
- Pydantic v2
- Alembic migrations
- Supabase/Postgres
- DB-first architecture: database is canonical

Testing rules:
- Prefer focused unit/integration tests over broad rewrites
- Reuse existing fixtures in tests/conftest.py where possible
- Preserve current architecture and naming conventions
- Validate enum values against DB-facing values, not enum member names
- Respect TIMESTAMPTZ/timezone-aware conventions
- Do not invent fields not present in the DB schema
- Keep tests minimal, deterministic, and readable

Workflow:
1. Inspect the target module and existing related tests
2. Identify missing happy-path, edge-case, and failure-path coverage
3. Add or update tests only where needed
4. Run only the relevant test subset first
5. If it passes, suggest broader suite commands
6. Report exactly what changed and why
