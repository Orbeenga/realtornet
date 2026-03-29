# Session Discipline for AI-Assisted Development

## Why this matters
AI agents degrade in context reliability beyond ~500-1000 lines of interaction.
They begin repeating fixes, forgetting conventions, and drifting from architecture rules.

## Rules for every session with Codex

### Before starting
- State the single bounded task explicitly
- Reference CLAUDE.md for architecture rules
- Specify which files are in scope - do not leave this open

### During the session
- One module boundary per task (model OR schema OR crud OR router - not all at once)
- If the task expands, stop and checkpoint before continuing
- If Codex invents a field or type not in the DB, stop immediately and correct

### At session end
- Run: /context_checkpoint (or use the context_checkpoint.md command)
- Commit the checkpoint summary to docs/agent-workflows/checkpoints/
- Run check_backend.sh and record pass/fail state
- Never leave a session with failing tests uncommitted

## Complexity guardrails
- Functions over 50 lines: flag for refactor
- Cyclomatic complexity over 5: flag for refactor
- Nesting depth over 2: refactor immediately
- Use radon cc app/ -a -nb to check after any significant edit

## Context reset signals
If Codex starts doing any of the following, reset the session:
- Repeating a fix it already applied
- Inventing fields or endpoints not previously discussed
- Suggesting create_all or schema-guessing patterns
- Generating code that ignores DB-first conventions
