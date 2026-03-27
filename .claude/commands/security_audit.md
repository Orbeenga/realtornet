Run a backend security audit for this Python project.

Workflow:
1. Inspect dependency files
2. Run Python dependency vulnerability checks if available
3. Review obvious security-sensitive areas:
   - auth/token handling
   - password/security utilities
   - file upload/storage logic
   - database session handling
   - secrets/config usage
4. Flag findings by severity
5. Suggest minimal safe fixes first
6. Do not perform large dependency upgrades without checking test impact
