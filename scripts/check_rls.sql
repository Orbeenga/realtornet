SELECT
    c.relname,
    c.relrowsecurity
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
      'agencies',
      'agent_profiles',
      'amenities',
      'favorites',
      'inquiries',
      'locations',
      'profiles',
      'properties',
      'property_amenities',
      'property_images',
      'property_types',
      'reviews',
      'saved_searches',
      'users'
  )
ORDER BY c.relname;

SELECT
    schemaname,
    tablename,
    policyname,
    roles,
    cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'agencies',
      'agent_profiles',
      'amenities',
      'favorites',
      'inquiries',
      'locations',
      'profiles',
      'properties',
      'property_amenities',
      'property_images',
      'property_types',
      'reviews',
      'saved_searches',
      'users'
  )
ORDER BY tablename, policyname;
