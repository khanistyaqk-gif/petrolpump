-- Run AFTER you created the first user in Supabase → Authentication → Users.
-- Replace the UUID (copy it from that user's row) and the name.
insert into public.profiles (id, name, role, is_active)
values ('PASTE-USER-UUID-HERE', 'Owner Name', 'owner', true)
on conflict (id) do update set role = 'owner', is_active = true;
