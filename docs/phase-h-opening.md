# Phase H Opening Template

Use this as the opening prompt when Phase H begins:

> Opening RealtorNet Phase H. Phase G closed April 29 2026 — all exit criteria met, commits d74806f (frontend) and e5efece (backend) pushed, CLAUDE.md committed to both repos.
> Backend v0.5.3+ on Railway. Frontend Next.js 16.2.1 on Vercel. Production Supabase: avkhpachzsbgmbnkfnhu. Dev Supabase umhtnqxdvffpifqbdtjs — do not use for production work. Production DB at migration head c8f3b2a91e44.
> First task — production cleanup verification: G.7 smoke records were soft-deleted on April 29 2026; verify agency_id=8, property_id=5, inquiry_id=5 remain soft-deleted and confirm the 4 real accounts are untouched. Related smoke artifacts also soft-deleted: agency_invitations.id=2, agency_agent_memberships.id=4, users 86/87/88.
> Phase H backlog (from DEFERRED.md): DEF-G-TBT-001 TBT < 100ms; DEF-G-POLYFILL-001 residual third-party core-js cleanup; DEF-002 audit log retention after 60 days real traffic; DEF-007 psycopg3 dev restart workaround; DEF-006 storage bucket provisioning and policy verification; agency owner onboarding self-service; advanced map view; admin analytics dashboard; saved search notifications; Nominatim/OSM geocoding; email notification service; agency aggregation optimization; custom domain setup.
> Attach Phase H workbook, DEFERRED.md, and all CLAUDE.md files available to the active repo/workspace.

## Cleanup Verification Query

```sql
select 'agency' as kind, agency_id::text as id, deleted_at is not null as deleted
from agencies
where agency_id = 8
union all
select 'property', property_id::text, deleted_at is not null
from properties
where property_id = 5
union all
select 'inquiry', inquiry_id::text, deleted_at is not null
from inquiries
where inquiry_id = 5
union all
select 'real_user', user_id::text, deleted_at is not null
from users
where email in (
  'apineorbeenga@gmail.com',
  'apineorbeenga@outlook.com',
  'apineorbeenga@yahoo.com',
  'godwinemagun@gmail.com'
);
```
