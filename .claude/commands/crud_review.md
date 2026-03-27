Review CRUD logic for: $ARGUMENTS

References:
- `CLAUDE.md`
- `PREFLIGHT.md`

Checklist:
- Soft delete filtering is enforced (`deleted_at IS NULL`).
- Audit fields are set (`created_by`, `updated_by`, `deleted_by`).
- Query immutability handled (reassign after `where`).
- Enum comparisons are case-insensitive and use enum values, not names.
- Pagination sanitizes negative `skip` and `limit`.
- No public `str(e)` exposure.

Output:
- Findings ordered by severity.
- Exact file paths and fixes.

Before submitting any file, verify commenting standard (CLAUDE.md section 9):
- First line is # file/path header
- Class bodies use # not """
- Every non-obvious column/relationship has inline # comment
- """ only inside def blocks, sparingly and can also be used to introduce a file after the # file/path header
