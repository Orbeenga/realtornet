-- database_rls_policies

CREATE POLICY "Enable update access for users based on supabase mapping" ON public.saved_searches FOR UPDATE TO public USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id()));
CREATE POLICY "Enable delete access for users based on supabase mapping" ON public.saved_searches FOR DELETE TO public USING ((user_id = current_user_id()));
CREATE POLICY "Public and Admin can read amenities" ON public.amenities FOR SELECT TO anon, authenticated, dashboard_user USING ((true OR (EXISTS ( SELECT 1
   FROM users
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true))))));
CREATE POLICY "Enable insert for authenticated users only" ON public.agent_profiles FOR INSERT TO public WITH CHECK ((user_id = current_user_id()));
CREATE POLICY "Enable update access for users based on supabase mapping" ON public.agent_profiles FOR UPDATE TO public USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id()));
CREATE POLICY "Enable delete access for users based on supabase mapping" ON public.agent_profiles FOR DELETE TO public USING ((user_id = current_user_id()));
CREATE POLICY "Insert amenities - admin only" ON public.amenities FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM users
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true))))); 
CREATE POLICY "Update amenities - admin only" ON public.amenities FOR UPDATE TO authenticated USING ((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true))))) WITH CHECK ((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true))))); 
CREATE POLICY "Delete amenities - admin only" ON public.amenities FOR DELETE TO authenticated USING ((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true)))));  
CREATE POLICY "View property types" ON public.property_types FOR SELECT TO public USING (true); 
CREATE POLICY "Insert property types (admins only)" ON public.property_types FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true)))));   
CREATE POLICY "Authenticated select agencies" ON public.agencies FOR SELECT TO authenticated USING (((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true)))) OR true));  
CREATE POLICY "Users select profiles" ON public.profiles FOR SELECT TO authenticated USING ((user_id = current_user_id())); 
CREATE POLICY "Users update profiles" ON public.profiles FOR UPDATE TO authenticated USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id()));  
CREATE POLICY "Admins insert profiles" ON public.profiles FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM users 
  WHERE ((users.user_id = profiles.user_id) AND (users.is_admin = true) AND (users.user_id = current_user_id())))));   
CREATE POLICY "Admins delete profiles" ON public.profiles FOR DELETE TO authenticated USING ((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = profiles.user_id) AND (users.is_admin = true) AND (users.user_id = current_user_id())))));  
CREATE POLICY "Enable read access for users based on supabase mapping" ON public.inquiries FOR SELECT TO public USING ((user_id = current_user_id()));  
CREATE POLICY "Enable insert for authenticated users only" ON public.inquiries FOR INSERT TO public WITH CHECK ((user_id = current_user_id()));   
CREATE POLICY "Enable update access for users based on supabase mapping" ON public.inquiries FOR UPDATE TO public USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id())); 
CREATE POLICY "Enable delete access for users based on supabase mapping" ON public.inquiries FOR DELETE TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Enable read access for users based on supabase mapping" ON public.reviews FOR SELECT TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Enable insert for authenticated users only" ON public.reviews FOR INSERT TO public WITH CHECK ((user_id = current_user_id())); 
CREATE POLICY "Enable update access for users based on supabase mapping" ON public.reviews FOR UPDATE TO public USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id())); 
CREATE POLICY "Enable delete access for users based on supabase mapping" ON public.reviews FOR DELETE TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Enable read access for users based on supabase mapping" ON public.saved_searches FOR SELECT TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Enable insert for authenticated users only" ON public.saved_searches FOR INSERT TO public WITH CHECK ((user_id = current_user_id())); 
CREATE POLICY "Enable read access for users based on supabase mapping" ON public.agent_profiles FOR SELECT TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Users can add favorites" ON public.favorites FOR INSERT TO public WITH CHECK ((user_id = current_user_id())); 
CREATE POLICY "Users can remove their own favorites" ON public.favorites FOR DELETE TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Users can view their own favorites" ON public.favorites FOR SELECT TO public USING ((user_id = current_user_id())); 
CREATE POLICY "Admins can manage property amenities" ON public.property_amenities FOR ALL TO public USING ((EXISTS ( SELECT 1 
   FROM users 
  WHERE ((users.user_id = current_user_id()) AND (users.is_admin = true))))); 
CREATE POLICY "Authenticated select users" ON public.users FOR SELECT TO authenticated USING ((is_admin OR (user_id = current_user_id()))); 
CREATE POLICY "Admins insert users" ON public.users FOR INSERT TO authenticated WITH CHECK (is_admin); 
CREATE POLICY "Admins delete users" ON public.users FOR DELETE TO authenticated USING (is_admin); 
CREATE POLICY "Users can manage images for their own properties" ON public.property_images FOR ALL TO public USING ((EXISTS ( SELECT 1 
   FROM (properties 
     JOIN users ON ((users.user_id = properties.user_id))) 
  WHERE ((properties.property_id = property_images.property_id) AND (users.user_id = current_user_id()))))); 
CREATE POLICY "Users can update their own user record" ON public.users FOR UPDATE TO authenticated USING ((user_id = current_user_id())) WITH CHECK ((user_id = current_user_id()));
CREATE OR REPLACE FUNCTION public.update_modified_column()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    -- explicitly set search_path
    SET search_path = public;

    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$function$;
