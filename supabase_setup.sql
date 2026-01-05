-- Create a table for public profiles using the 'users' table in auth schema
create table public.profiles (
  id uuid references auth.users not null primary key,
  email text,
  role text default 'user',
  is_approved boolean default false,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable Row Level Security (RLS)
alter table public.profiles enable row level security;

-- Create policies
-- 1. Public profiles are viewable by everyone (or restrict to authenticated users if preferred)
create policy "Public profiles are viewable by everyone"
  on profiles for select
  using ( true );

-- 2. Users can insert their own profile
create policy "Users can insert their own profile"
  on profiles for insert
  with check ( auth.uid() = id );

-- 3. Users can update own profile
create policy "Users can update own profile"
  on profiles for update
  using ( auth.uid() = id );

-- Function to handle new user signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, role, is_approved)
  values (new.id, new.email, 'user', false);
  return new;
end;
$$ language plpgsql security definer;

-- Trigger to call the function on a new user creation
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Optional: Initial Admin insertion (Replace 'your-email@example.com' with your actual email)
-- You can run this AFTER you have signed up once to make yourself approved immediately.
-- update public.profiles set is_approved = true, role = 'admin' where email = 'your-email@example.com';
