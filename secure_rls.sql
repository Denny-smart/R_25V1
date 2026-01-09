-- Helper Function to check Admin status (Security Definer to avoid RLS recursion)
create or replace function public.is_admin()
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
  return exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
end;
$$;

-- Function to clean up auth.users when profile is deleted
create or replace function public.delete_user_from_auth()
returns trigger 
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from auth.users where id = old.id;
  return old;
end;
$$;

-- Create the trigger on the profiles table
drop trigger if exists on_profile_delete on public.profiles;
create trigger on_profile_delete
  after delete on public.profiles
  for each row execute procedure public.delete_user_from_auth();

-- Fix security warning for existing handle_new_user function if it exists
do $$
begin
  if exists (select 1 from pg_proc where proname = 'handle_new_user') then
    alter function public.handle_new_user() set search_path = public;
  end if;
end $$;

-- Enable RLS
alter table public.profiles enable row level security;

-- CLEANUP: Drop all previous versions of policies
drop policy if exists "Admins can delete profiles" on public.profiles;
drop policy if exists "Profiles visible to owner and admins" on public.profiles;
drop policy if exists "Public profiles are viewable by everyone" on public.profiles; 
drop policy if exists "Admins can update any profile" on public.profiles;
drop policy if exists "Users can update own profile" on public.profiles;
drop policy if exists "Admins or owners can update profile" on public.profiles;
drop policy if exists "Users can insert their own profile" on public.profiles;

-- DELETE Policy (Admins only)
create policy "Admins can delete profiles"
  on public.profiles
  for delete
  using ( (select public.is_admin()) );

-- SELECT Policy (Combined: Admin OR Owner)
create policy "Profiles visible to owner and admins"
  on public.profiles
  for select
  using (
    (select auth.uid()) = id
    or
    (select public.is_admin())
  );

-- UPDATE Policy (Combined: Admin OR Owner)
create policy "Admins or owners can update profile"
  on public.profiles
  for update
  using (
    (select auth.uid()) = id
    or
    (select public.is_admin())
  );

-- INSERT Policy (Users can insert own profile)
create policy "Users can insert their own profile"
  on public.profiles
  for insert
  with check ( (select auth.uid()) = id );
