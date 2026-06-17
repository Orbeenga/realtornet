-- Hard-delete test accounts user_id 13-44 in dependency order
-- Run in Supabase SQL editor against PRODUCTION (fobvnshrqxduuhzgflvd)
-- RUN EACH SECTION IN ORDER; verify output before proceeding.

-- ============================================================================
-- SECTION 0: Guard — ensure ENV=production confirmation
-- ============================================================================
-- !! UNCOMMENT and run first to confirm environment:
-- SELECT current_database(), inet_server_addr(), current_user;

-- ============================================================================
-- SECTION 1: Preview — which user_ids 13-44 actually exist?
-- ============================================================================

SELECT user_id, email, user_role, supabase_id, is_verified, created_at, deleted_at
FROM users
WHERE user_id BETWEEN 13 AND 44
ORDER BY user_id;

-- ============================================================================
-- SECTION 2: Check for real inquiry activity on test-user properties
-- ============================================================================

-- 2a. Properties owned by users 13-44
SELECT p.property_id, p.user_id, p.title, p.moderation_status, p.listing_status,
       u.email AS owner_email
FROM properties p
JOIN users u ON u.user_id = p.user_id
WHERE p.user_id BETWEEN 13 AND 44
  AND p.deleted_at IS NULL
ORDER BY p.user_id, p.property_id;

-- 2b. Inquiries on those properties (real engagement)
SELECT i.inquiry_id, i.property_id, i.user_id AS inquirer_id,
       i.inquiry_status, i.message, i.created_at,
       p.title AS property_title,
       u.email AS property_owner_email
FROM inquiries i
JOIN properties p ON p.property_id = i.property_id
JOIN users u ON u.user_id = p.user_id
WHERE p.user_id BETWEEN 13 AND 44
  AND i.deleted_at IS NULL
ORDER BY i.property_id, i.created_at;

-- ============================================================================
-- SECTION 3: Dependency preview — count rows per table for users 13-44
-- ============================================================================

WITH target_users AS (
    SELECT user_id FROM users WHERE user_id BETWEEN 13 AND 44
)
SELECT 'agent_membership_audit' AS tbl, count(*) FROM agent_membership_audit WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'agency_invitations', count(*) FROM agency_invitations WHERE invited_user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'agency_agent_memberships', count(*) FROM agency_agent_memberships WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'agency_join_requests', count(*) FROM agency_join_requests WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'agency_membership_review_requests', count(*) FROM agency_membership_review_requests WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'agent_profiles', count(*) FROM agent_profiles WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'profiles', count(*) FROM profiles WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'saved_searches', count(*) FROM saved_searches WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'favorites', count(*) FROM favorites WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'inquiries', count(*) FROM inquiries WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'reviews_by', count(*) FROM reviews WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'reviews_on', count(*) FROM reviews WHERE agent_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'review_requests', count(*) FROM review_requests WHERE user_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'listing_events_by', count(*) FROM listing_events WHERE actor_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'listing_instructions_by', count(*) FROM listing_instructions WHERE actor_id IN (SELECT user_id FROM target_users)
UNION ALL
SELECT 'properties', count(*) FROM properties WHERE user_id IN (SELECT user_id FROM target_users)
ORDER BY tbl;

-- ============================================================================
-- SECTION 4: If Section 2b returned inquiry rows with real messages → ABORT
--            and use soft-delete fallback script instead.
--            If Section 2b is empty or only system/test inquiries, proceed.
-- ============================================================================

-- ============================================================================
-- SECTION 5: HARD DELETE in dependency order
-- ============================================================================

-- UNCOMMENT and run SECTION 5 as a single transaction:

/*
BEGIN;

WITH target_users AS (
    SELECT user_id FROM users WHERE user_id BETWEEN 13 AND 44
)
-- 5a. listing_instructions (actor_id)
DELETE FROM listing_instructions WHERE actor_id IN (SELECT user_id FROM target_users);

-- 5b. listing_events (actor_id SET NULL — explicit NULL first, then delete orphaned)
UPDATE listing_events SET actor_id = NULL WHERE actor_id IN (SELECT user_id FROM target_users);
DELETE FROM listing_events WHERE actor_id IS NULL AND listing_id IS NULL;

-- 5c. agent_membership_audit (user_id CASCADE, actor_id SET NULL)
UPDATE agent_membership_audit SET actor_id = NULL WHERE actor_id IN (SELECT user_id FROM target_users);
DELETE FROM agent_membership_audit WHERE user_id IN (SELECT user_id FROM target_users);

-- 5d. agency_membership_review_requests
UPDATE agency_membership_review_requests SET decided_by = NULL WHERE decided_by IN (SELECT user_id FROM target_users);
DELETE FROM agency_membership_review_requests WHERE user_id IN (SELECT user_id FROM target_users);

-- 5e. agency_invitations
UPDATE agency_invitations SET invited_user_id = NULL WHERE invited_user_id IN (SELECT user_id FROM target_users);

-- 5f. agency_agent_memberships
UPDATE agency_agent_memberships SET status_decided_by = NULL WHERE status_decided_by IN (SELECT user_id FROM target_users);
DELETE FROM agency_agent_memberships WHERE user_id IN (SELECT user_id FROM target_users);

-- 5g. agency_join_requests
UPDATE agency_join_requests SET decided_by = NULL WHERE decided_by IN (SELECT user_id FROM target_users);
DELETE FROM agency_join_requests WHERE user_id IN (SELECT user_id FROM target_users);

-- 5h. review_requests
UPDATE review_requests SET actor_id = NULL WHERE actor_id IN (SELECT user_id FROM target_users);
DELETE FROM review_requests WHERE user_id IN (SELECT user_id FROM target_users);

-- 5i. reviews (user_id, agent_id)
DELETE FROM reviews WHERE user_id IN (SELECT user_id FROM target_users);
DELETE FROM reviews WHERE agent_id IN (SELECT user_id FROM target_users);

-- 5j. favorites
DELETE FROM favorites WHERE user_id IN (SELECT user_id FROM target_users);

-- 5k. inquiries (user_id)
DELETE FROM inquiries WHERE user_id IN (SELECT user_id FROM target_users);

-- 5l. saved_searches
DELETE FROM saved_searches WHERE user_id IN (SELECT user_id FROM target_users);

-- 5m. properties (user_id)
DELETE FROM properties WHERE user_id IN (SELECT user_id FROM target_users);

-- 5n. agent_profiles (user_id CASCADE)
DELETE FROM agent_profiles WHERE user_id IN (SELECT user_id FROM target_users);

-- 5o. profiles (user_id)
DELETE FROM profiles WHERE user_id IN (SELECT user_id FROM target_users);

-- 5p. users
DELETE FROM users WHERE user_id IN (SELECT user_id FROM target_users);

COMMIT;
*/

-- ============================================================================
-- SECTION 6: Supabase Auth cleanup
-- ============================================================================

-- Run this AFTER Section 5 to get the supabase_ids for API-based deletion
/*
SELECT user_id, email, supabase_id
FROM users
WHERE user_id BETWEEN 13 AND 44
ORDER BY user_id;
*/

-- For each supabase_id above, run in Supabase dashboard SQL editor:
--   select supabase.auth.admin.delete_user('<supabase_id>');
-- OR via Management API:
--   DELETE https://fobvnshrqxduuhzgflvd.supabase.co/auth/v1/admin/users/<supabase_id>
--   Headers: Authorization: Bearer <service_role_key>

-- ============================================================================
-- SECTION 7: Post-run verification
-- ============================================================================

SELECT COUNT(*) AS active_user_count
FROM users
WHERE deleted_at IS NULL;

SELECT user_id, email, user_role
FROM users
WHERE email IN (
    'apineorbeenga@gmail.com',
    'apineorbeenga@outlook.com',
    'apineorbeenga@yahoo.com',
    'apineterngu19@gmail.com'
)
ORDER BY user_id;
