Audit dependencies for this repo using the project standards in `CLAUDE.md` and `PREFLIGHT.md`.

Steps:
1. If `requirements.txt` exists, run `pip-audit -r requirements.txt`.
2. If `pyproject.toml` defines dependencies, run `pip-audit` for that environment too.
3. Summarize findings and propose upgrades.
4. If fixes are applied, run relevant tests and report results.

Notes:
- If `pip-audit` is not installed, say so and suggest installing it first.