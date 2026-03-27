Validate this local app flow in the browser: $ARGUMENTS

Workflow:
1. Start or confirm the local application is running
2. Open the relevant page/flow
3. Reproduce the issue or inspect the behavior
4. Check for:
   - console errors
   - failing network requests
   - broken auth/session state
   - permission issues
   - incorrect redirects
   - form validation problems
5. Apply the smallest correct fix
6. Re-test the exact flow
7. Summarize root cause, file changes, and residual risks

Project rules:
- Keep fixes lean
- Respect DB-first architecture
- Do not invent fields or routes
- Prefer reproducible flows over assumptions
