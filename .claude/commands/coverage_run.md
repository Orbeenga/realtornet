Run the standard coverage command for this repo.

Command:
pytest tests/ --cov=app --cov-report=term-missing -x --tb=short

Notes:
- If coverage fails to collect due to peripheral errors, re-run with `--ignore` for those paths and report what was ignored.