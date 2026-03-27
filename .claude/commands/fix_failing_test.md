Debug and fix this failing test or test module: $ARGUMENTS

Workflow:
1. Reproduce the failure
2. Isolate whether the issue is in:
   - fixture setup
   - test expectation
   - schema/model mismatch
   - auth/token payload
   - enum/value serialization
   - DB transaction handling
3. Apply the smallest correct fix
4. Re-run the failing test(s)
5. Explain root cause clearly and precisely
Do not silently change assertions unless the test is truly wrong.
