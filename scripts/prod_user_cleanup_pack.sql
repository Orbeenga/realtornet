-- Production user cleanup pack
--
-- Purpose:
-- 1. Preview which user rows would be treated as disposable test data.
-- 2. Preview all dependent records tied to those users before any soft delete.
-- 3. Soft-delete only the candidate user rows once the preview looks correct.
--
-- Safety rule:
-- This pack preserves the only real accounts currently approved for retention.
-- Update the allowlist below before running in any other environment.

-- ---------------------------------------------------------------------------
-- Section 1: Preserve list and candidate preview
-- ---------------------------------------------------------------------------

WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT
        u.user_id,
        u.email,
        u.supabase_id,
        u.user_role,
        u.agency_id,
        u.created_at,
        u.deleted_at
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT *
FROM candidate_users
ORDER BY user_id;

-- ---------------------------------------------------------------------------
-- Section 2: High-level dependency summary
-- ---------------------------------------------------------------------------

WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
),
candidate_properties AS (
    SELECT p.property_id
    FROM properties p
    WHERE p.deleted_at IS NULL
      AND p.user_id IN (SELECT user_id FROM candidate_users)
)
SELECT 'users' AS table_name, count(*) AS affected_rows
FROM users
WHERE user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'profiles', count(*)
FROM profiles
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'agent_profiles', count(*)
FROM agent_profiles
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'properties', count(*)
FROM properties
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'favorites_by_candidate_user', count(*)
FROM favorites
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'favorites_on_candidate_properties', count(*)
FROM favorites
WHERE deleted_at IS NULL
  AND property_id IN (SELECT property_id FROM candidate_properties)
UNION ALL
SELECT 'inquiries_by_candidate_user', count(*)
FROM inquiries
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'inquiries_on_candidate_properties', count(*)
FROM inquiries
WHERE deleted_at IS NULL
  AND property_id IN (SELECT property_id FROM candidate_properties)
UNION ALL
SELECT 'saved_searches', count(*)
FROM saved_searches
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'reviews_authored_by_candidate_user', count(*)
FROM reviews
WHERE deleted_at IS NULL
  AND user_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'reviews_received_by_candidate_agent', count(*)
FROM reviews
WHERE deleted_at IS NULL
  AND agent_id IN (SELECT user_id FROM candidate_users)
UNION ALL
SELECT 'reviews_on_candidate_properties', count(*)
FROM reviews
WHERE deleted_at IS NULL
  AND property_id IN (SELECT property_id FROM candidate_properties)
UNION ALL
SELECT 'property_images_on_candidate_properties', count(*)
FROM property_images
WHERE property_id IN (SELECT property_id FROM candidate_properties)
UNION ALL
SELECT 'property_amenities_on_candidate_properties', count(*)
FROM property_amenities
WHERE property_id IN (SELECT property_id FROM candidate_properties)
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- Section 3: Detailed dependency previews
-- ---------------------------------------------------------------------------

-- 3a. Profiles tied to candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT p.profile_id, p.user_id, cu.email, p.full_name, p.status, p.created_at
FROM profiles p
JOIN candidate_users cu ON cu.user_id = p.user_id
WHERE p.deleted_at IS NULL
ORDER BY p.user_id, p.profile_id;

-- 3b. Agent profiles tied to candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT ap.profile_id, ap.user_id, cu.email, ap.agency_id, ap.company_name, ap.created_at
FROM agent_profiles ap
JOIN candidate_users cu ON cu.user_id = ap.user_id
WHERE ap.deleted_at IS NULL
ORDER BY ap.user_id, ap.profile_id;

-- 3c. Properties owned by candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT p.property_id, p.user_id, cu.email, p.title, p.is_verified, p.listing_status, p.created_at
FROM properties p
JOIN candidate_users cu ON cu.user_id = p.user_id
WHERE p.deleted_at IS NULL
ORDER BY p.user_id, p.property_id;

-- 3d. Favorites created by candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT f.user_id, cu.email, f.property_id, f.created_at
FROM favorites f
JOIN candidate_users cu ON cu.user_id = f.user_id
WHERE f.deleted_at IS NULL
ORDER BY f.user_id, f.property_id;

-- 3e. Favorites attached to candidate-owned properties
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
),
candidate_properties AS (
    SELECT p.property_id, p.user_id, p.title
    FROM properties p
    WHERE p.deleted_at IS NULL
      AND p.user_id IN (SELECT user_id FROM candidate_users)
)
SELECT f.user_id AS favoriting_user_id,
       cp.user_id AS property_owner_user_id,
       cu.email AS property_owner_email,
       cp.property_id,
       cp.title,
       f.created_at
FROM favorites f
JOIN candidate_properties cp ON cp.property_id = f.property_id
JOIN candidate_users cu ON cu.user_id = cp.user_id
WHERE f.deleted_at IS NULL
ORDER BY cp.user_id, cp.property_id, f.user_id;

-- 3f. Inquiries created by candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT i.inquiry_id, i.user_id, cu.email, i.property_id, i.inquiry_status, i.created_at
FROM inquiries i
JOIN candidate_users cu ON cu.user_id = i.user_id
WHERE i.deleted_at IS NULL
ORDER BY i.user_id, i.inquiry_id;

-- 3g. Inquiries attached to candidate-owned properties
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
),
candidate_properties AS (
    SELECT p.property_id, p.user_id, p.title
    FROM properties p
    WHERE p.deleted_at IS NULL
      AND p.user_id IN (SELECT user_id FROM candidate_users)
)
SELECT i.inquiry_id,
       i.user_id AS inquirer_user_id,
       cp.user_id AS property_owner_user_id,
       cu.email AS property_owner_email,
       cp.property_id,
       cp.title,
       i.inquiry_status,
       i.created_at
FROM inquiries i
JOIN candidate_properties cp ON cp.property_id = i.property_id
JOIN candidate_users cu ON cu.user_id = cp.user_id
WHERE i.deleted_at IS NULL
ORDER BY cp.user_id, cp.property_id, i.inquiry_id;

-- 3h. Saved searches owned by candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT s.search_id, s.user_id, cu.email, s.name, s.created_at
FROM saved_searches s
JOIN candidate_users cu ON cu.user_id = s.user_id
WHERE s.deleted_at IS NULL
ORDER BY s.user_id, s.search_id;

-- 3i. Reviews authored by candidate users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT r.review_id, r.user_id, cu.email, r.agent_id, r.property_id, r.rating, r.created_at
FROM reviews r
JOIN candidate_users cu ON cu.user_id = r.user_id
WHERE r.deleted_at IS NULL
ORDER BY r.user_id, r.review_id;

-- 3j. Reviews received by candidate-agent users
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
SELECT r.review_id, r.agent_id, cu.email, r.user_id AS reviewer_user_id, r.property_id, r.rating, r.created_at
FROM reviews r
JOIN candidate_users cu ON cu.user_id = r.agent_id
WHERE r.deleted_at IS NULL
ORDER BY r.agent_id, r.review_id;

-- 3k. Property images attached to candidate-owned properties
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
),
candidate_properties AS (
    SELECT p.property_id, p.user_id, p.title
    FROM properties p
    WHERE p.deleted_at IS NULL
      AND p.user_id IN (SELECT user_id FROM candidate_users)
)
SELECT pi.image_id, cp.user_id, cu.email, cp.property_id, cp.title, pi.image_url, pi.is_primary
FROM property_images pi
JOIN candidate_properties cp ON cp.property_id = pi.property_id
JOIN candidate_users cu ON cu.user_id = cp.user_id
ORDER BY cp.user_id, cp.property_id, pi.image_id;

-- 3l. Property amenities attached to candidate-owned properties
WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id, u.email
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
),
candidate_properties AS (
    SELECT p.property_id, p.user_id, p.title
    FROM properties p
    WHERE p.deleted_at IS NULL
      AND p.user_id IN (SELECT user_id FROM candidate_users)
)
SELECT pa.property_id, cp.user_id, cu.email, cp.title, pa.amenity_id
FROM property_amenities pa
JOIN candidate_properties cp ON cp.property_id = pa.property_id
JOIN candidate_users cu ON cu.user_id = cp.user_id
ORDER BY cp.user_id, pa.property_id, pa.amenity_id;

-- ---------------------------------------------------------------------------
-- Section 4: Execution block
-- ---------------------------------------------------------------------------
--
-- This block only soft-deletes user rows.
-- It does NOT automatically soft-delete dependent records. Review the previews
-- above first, then decide whether any linked domain records should also be
-- soft-deleted in a second pass.
--
-- Recommended usage:
-- 1. Run the preview sections first.
-- 2. Confirm the candidate list is correct.
-- 3. Wrap the update below in a transaction in the Supabase SQL editor.

/*
BEGIN;

WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
),
candidate_users AS (
    SELECT u.user_id
    FROM users u
    WHERE u.deleted_at IS NULL
      AND lower(u.email) NOT IN (
          SELECT lower(email) FROM preserved_emails
      )
)
UPDATE users
SET deleted_at = now()
WHERE user_id IN (SELECT user_id FROM candidate_users)
  AND deleted_at IS NULL;

COMMIT;
*/

-- ---------------------------------------------------------------------------
-- Section 5: Post-run verification
-- ---------------------------------------------------------------------------

WITH preserved_emails(email) AS (
    VALUES
        ('apineorbeenga@gmail.com'),
        ('godwinemagun@gmail.com'),
        ('apineorbeenga@outlook.com'),
        ('apineorbeenga@yahoo.com')
)
SELECT user_id, email, user_role, created_at, deleted_at
FROM users
WHERE lower(email) NOT IN (
    SELECT lower(email) FROM preserved_emails
)
ORDER BY user_id;

