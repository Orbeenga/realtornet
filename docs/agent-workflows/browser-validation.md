# Browser Validation Workflow

Use this workflow when validating RealtorNet behavior locally.

## Goals
- Verify actual browser behavior, not just source code
- Catch integration issues across frontend/backend boundaries
- Reproduce bugs before changing code
- Re-test after fixes

## Standard sequence
1. Start the local app/services needed for the target flow
2. Open the relevant page in the browser
3. Reproduce the issue or exercise the target flow
4. Observe:
   - console errors
   - failed requests
   - broken navigation
   - auth/session issues
   - form validation behavior
   - unexpected UI/backend responses
5. Fix the smallest correct issue
6. Re-run the flow
7. Document what failed, why, and what changed

## Priority flows for RealtorNet
- Authentication / protected routes
- Profile and agency flows
- Property create/edit/view flows
- Saved searches / favorites
- Inquiry submission paths
- Error-state and permission-boundary checks

## Rules
- Do not assume success from code inspection alone
- Prefer reproducible flows
- Keep changes lean and architecture-consistent
- Pair browser validation with pytest when backend logic is involved
