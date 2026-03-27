Review the current branch as if this were a pull request.

Focus on:
- DB-first correctness
- ORM/schema/router alignment
- migration safety
- enum correctness
- auth/token consistency
- test impact
- RLS/security implications

Use RealtorNet repo standards from CLAUDE.md.
Return:
1. critical issues
2. medium-risk issues
3. suggested tests
4. minimal fix plan