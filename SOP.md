# RealtorNet Agent Standard Operating Procedure

Applies to: Every agent (Cursor, Windsurf, Copilot, or any other) working on
any RealtorNet repository. This is law. No exceptions, no workarounds.

---

## Before writing any code

1. Read CLAUDE.md (root, then repo-specific). List every locked state
   explicitly before proceeding.
2. If your planned change touches a file containing a locked state, stop
   and report before proceeding.
3. Output a pre-flight confirmation block listing at least 5 locked rules
   from PREFLIGHT.md. Attaching PREFLIGHT.md is not sufficient — the
   declaration proves it was read.
4. Run `pnpm gen:types` (frontend) or confirm schema is current (backend)
   before writing any hook, endpoint, or type that touches the API contract.
   `gen:types` must resolve against a live deployed backend, not a pending one.

---

## Before every commit

**Backend gates — all three must pass, in this order:**

```bash
python -m pyright app/        # must return 0 errors
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
$env:PYTHONPATH = "."
python -m pytest --cov=app --cov-fail-under=95.0 -q   # all passing, coverage ≥ 95.00%
```

Local test target is Docker PostGIS (`local-postgis` container, `testdb`
database). Never run the full test suite against remote Supabase staging —
it takes 2-3 hours and produces connection instability. If the Docker
container is not running: `docker start local-postgis`.

**Frontend gates — all three must pass, in this order:**

```bash
pnpm exec tsc --noEmit        # must return 0 errors
pnpm lint                     # must return 0 warnings
pnpm build                    # must return 0 warnings
```

If any gate fails, fix before committing. Never commit to unblock — fix
the root cause.

---

## Commit discipline

- One commit per logical unit of work. Never bundle unrelated fixes.
- Never push via GitHub API or any path that bypasses local gate execution.
- Never force push to main.
- If local is behind remote: `git pull --rebase origin main` before
  committing. Resolve conflicts, re-run gates, then push.
- Commit message must name the task (e.g. `T.3: correct revoked label and
  roster filter`), not describe the method.
- `detect-secrets` pre-commit hook is active on the backend repo. Any commit
  containing a credential pattern is blocked automatically. Never hardcode
  connection strings, API keys, or passwords in committed files.

---

## Deploy order (non-negotiable)

Backend commit → push → wait for Railway deploy (green `/healthz`) →
`pnpm gen:types` against production OpenAPI → if types changed, commit
gen:types result → push → frontend logic changes.

Never commit backend and frontend in the same batch. Never run `gen:types`
against a pending backend that has not yet deployed.

---

## Migration discipline (backend)

- Every Alembic migration must have `down_revision` set to the actual
  revision ID — never the filename.
- Verify the parent revision ID with `alembic history` before writing
  `down_revision`.
- Migrations run via `preDeployCommand` in `railway.toml` — never inline
  in `startCommand`.
- Never commit a migration without confirming the revision chain is intact
  locally first.
- All trigger functions, utility functions, and scheduled job procedures
  must be created in the `internal` schema, never `public`. `public` is
  the PostgREST API exposure layer. See PREFLIGHT.md PostgREST Schema
  Topology Standard.

---

## When blocked

- If a task depends on another agent's work that is not live yet: stop,
  document the dependency explicitly in DEFERRED.md with the blocking item
  ID, and report back. Do not implement workarounds or hardcode values.
- If a file you need to edit already exists and your tool only creates new
  files: use a terminal write command to replace it in one operation. Do
  not patch sections of a file being rearchitected — partial patches cause
  partial-apply failures.
- If Docker PostGIS is unavailable for pytest: do not push. Start the
  container (`docker start local-postgis`) and confirm the test database
  exists before running gates. If truly unavailable, explicitly flag this
  before committing and get approval. Never substitute remote Supabase
  staging as a pytest target.
- The pytest command now requires the env var — agents running on Windows
  need $env:TEST_DATABASE_URL = ... before pytest, on Linux/Mac it's
  TEST_DATABASE_URL=... python -m pytest. Always confirm which shell you
  will default to and adjust accordingly.

---

## What never to do

- Never hardcode values that belong in the API contract or constants files.
- Never remove existing UI sections to make room for new ones — add
  alongside, never replace.
- Never touch `apiClient.ts` auth intercept logic (silent JWT refresh is
  a locked state).
- Never use the dev Supabase project (`umhtnqxdvffpifqbdtjs`) for any
  production diagnostics or work.
- Never touch production users (emails: apineorbeenga@gmail.com,
  apineorbeenga@outlook.com, apineorbeenga@yahoo.com, apineterngu19@gmail.com).
- Never delete from or update any append-only table:
  `agent_membership_audit`, `listing_events`, `listing_instructions`,
  `notifications`, `inquiry_replies`.
- Never use `str(ModerationStatus.x)` in API responses or dict keys —
  always use `.value`. `str()` produces `"ModerationStatus.x"` which
  breaks serialization silently.
- Never place trigger functions, utility functions, or scheduled job
  procedures in the `public` schema — use `internal`. PostgREST exposes
  everything in `public` via REST.
- Never run `alembic upgrade head` against the production Supabase project
  manually — Railway's `preDeployCommand` handles this automatically on
  every deploy.
- Never commit diagnostic scripts, one-off queries, or ad-hoc database
  checks to the repo. Run locally, read output, delete the file.
