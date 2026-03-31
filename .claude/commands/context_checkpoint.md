Produce a session checkpoint summary for this working session.

## Section 1: Session Summary
1. Files created or modified (exact paths)
2. Key decisions made and why
3. Patterns or conventions established or confirmed
4. Pending items not yet addressed
5. Any assumptions made that need verification
6. Current migration revision (run: python -m alembic current)
7. Test status (run: pytest tests/ -q and summarize)

Keep Section 1 under 200 words. Be precise, not comprehensive.

## Section 2: Memory Block (copy this to the next session opening)
Output a block in exactly this format:

## Memory (Carry Forward)
- Migration state: [current alembic revision hash]
- Last files touched: [list]
- Active conventions confirmed this session: [list]
- Decisions made: [list - e.g. "uq_agencies_email dropped as constraint not index"]
- Do not repeat: [list of fixes already applied this session]
- Pending: [list of items not yet done]
- Test state: [passing / N failing - specify which]

This memory block must be pasted at the top of the next session prompt
so the agent never contradicts or repeats prior work.
