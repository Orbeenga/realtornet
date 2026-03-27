Review DB-to-backend alignment for: $ARGUMENTS

Audit for:
- ORM fields vs actual DB columns
- Enum consistency
- PK/FK type parity
- nullability mismatches
- timestamptz handling
- server defaults
- soft-delete conventions
- router/schema/crud drift from DB truth

Output format:
1. Misalignments found
2. Risk level for each
3. Exact file-level fixes recommended
4. Safe order to apply fixes
Do not rewrite broadly unless necessary.
