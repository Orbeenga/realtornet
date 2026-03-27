Review or draft RLS for: $ARGUMENTS

RLS context:
- Supabase Auth
- auth.uid() maps to internal users.supabase_id
- Internal business keys are integer IDs
- Prefer helper-function based policies where already established
- Avoid repeated per-row auth evaluation patterns
- Use fully qualified references where appropriate

Output:
1. Table-by-table policy intent
2. Read/insert/update/delete policy recommendations
3. Performance or security concerns
4. SQL changes in safe order
Do not assume old policies are correct.
