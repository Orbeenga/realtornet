# Phase K — Production Data Quality Verification (E.1–E.3)

Run these queries in Supabase SQL editor against production DB (avkhpachzsbgmbnkfnhu):

## E.1: Verify smoke users are hard-deleted

```sql
-- Find any remaining smoke/generic users (should be empty if E.1 complete)
SELECT user_id, display_name, email, deleted_at
FROM users
WHERE deleted_at IS NULL
AND (
  display_name ~ '^Agent\s*#?\d+' OR
  display_name ~ '^A#\d+' OR
  display_name IS NULL OR
  display_name = ''
)
ORDER BY user_id;
```

**Expected:** Empty result set (all smoke users deleted except real users 5, 74, 76, 85, 89)

---

## E.2: Verify user_id=74 data consistency

```sql
-- Check membership count for user 74
SELECT 'membership' AS check_type, COUNT(*) as count, 
       STRING_AGG(DISTINCT status::text, ',') as statuses
FROM agency_agent_memberships 
WHERE user_id = 74 
GROUP BY user_id;

-- Check agent profile for user 74
SELECT 'agent_profile' AS check_type, COUNT(*) as count, 
       MAX(agency_id) as agency_id
FROM agent_profiles 
WHERE user_id = 74 AND deleted_at IS NULL;

-- Check user record
SELECT 'user_record' AS check_type, COUNT(*) as count,
       user_role, agency_id
FROM users 
WHERE id = 74 AND deleted_at IS NULL;
```

**Expected:** 
- 1 active membership (status='active', deleted_at IS NULL) for agency_id=9
- 1 agent_profile with agency_id=9
- 1 user record with user_role='agency_owner', agency_id=9

**Status:** promotion_data_repair complete if all three align on agency_id=9

---

## E.3: Verify property 3 listing_type is correct

```sql
SELECT id, title, listing_type, moderation_status, deleted_at
FROM properties 
WHERE id = 3 AND deleted_at IS NULL;
```

**Expected:** 
- `listing_type = 'for_rent'` (title mentions "for Rent")
- `moderation_status = 'verified'`

**Status:** listing_type_fix complete if listing_type='for_rent'

---

## Next Steps

1. Run all three query groups in Supabase SQL editor
2. Verify results match "Expected" status
3. If any fail, execute corresponding fix from Phase K Opening Brief
4. Document results in ticket or GitHub issue
