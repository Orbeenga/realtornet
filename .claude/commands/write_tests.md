Write comprehensive tests for: $ARGUMENTS

References:
- `CLAUDE.md`
- `PREFLIGHT.md`

Testing conventions:
- Use Pytest.
- Centralize fixtures in `tests/conftest.py`.
- Use `flush()` in fixtures, never `commit()`.
- Exclude soft-deleted records in queries.
- For geospatial WKT, always use `POINT(lon lat)`.
- Convert km to meters for `ST_DWithin`.
- Use `PYTHONPATH="."` if Windows import resolution is flaky.

Coverage expectations:
- Happy paths.
- Edge cases.
- Error states.

Naming:
- `tests/<area>/test_<feature>.py`
- `test_<operation>_<scenario>`