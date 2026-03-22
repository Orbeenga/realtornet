Run a preflight compliance pass for: $ARGUMENTS

References:
- `CLAUDE.md`
- `PREFLIGHT.md`

Rules:
- Enforce DB <-> ORM parity.
- Confirm soft delete filtering in queries.
- Verify enum handling uses `create_type=False` and `values_callable`.
- Ensure `updated_by` and `deleted_by` are tracked with Supabase UUIDs.
- Never expose `str(e)` in public errors.

Output:
- List violations with file paths.
- Provide exact fixes with code snippets.

Before submitting any file, verify commenting standard (CLAUDE.md section 9):
- First line is # file/path header
- Class bodies use # not """
- Every non-obvious column/relationship has inline # comment
- """ only inside def blocks, sparingly
