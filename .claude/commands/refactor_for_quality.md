Refactor this module or function for quality and simplicity: $ARGUMENTS

Constraints (enforce strictly):
- Maximum function length: 50 lines
- Maximum cyclomatic complexity: 5 per function
- Maximum nesting depth: 2 levels
- No nested loops where a built-in or comprehension suffices
- No duplicate logic blocks - extract shared patterns into helpers
- No unused imports, variables, or dead code
- No hardcoded values - use config/settings/enums

RealtorNet-specific rules:
- Do not invent fields not in DB schema
- Preserve PK/FK type parity
- Keep enum values DB-aligned
- Do not change function signatures unless clearly broken
- Do not refactor across module boundaries in one pass

Workflow:
1. Identify the single highest-complexity or most repetitive section
2. Apply the smallest correct refactor
3. Confirm tests still pass
4. Report: what changed, complexity before/after, any residual issues

Do not rewrite broadly. One clear improvement per pass.
