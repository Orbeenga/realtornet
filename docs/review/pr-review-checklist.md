# RealtorNet PR Review Checklist

## Architecture
- Does this preserve DB-first truth?
- Any phantom backend fields?
- Any schema/model/router drift?

## Database
- PK/FK type parity preserved?
- Enums match DB values exactly?
- Timezone-aware datetime conventions preserved?
- Migration sequencing safe?

## Security
- Auth/token handling still correct?
- RLS assumptions changed?
- Secrets/config handled safely?

## Testing
- Are changed paths covered by tests?
- Are assertions aligned with actual enum/database values?
- Are failures likely due to fixture drift or real behavior change?

## Change discipline
- Is the fix narrow and reversible?
- Any unnecessary refactor bundled with the change?