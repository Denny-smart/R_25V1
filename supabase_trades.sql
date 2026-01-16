-- Create trades table to persist trade history
create table if not exists public.trades (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users not null,
  contract_id text not null,
  symbol text not null,
  signal text not null,
  stake numeric,
  entry_price numeric,
  exit_price numeric,
  profit numeric,
  status text,
  timestamp timestamptz default now(),
  created_at timestamptz default now(),
  unique(contract_id)
);

-- Enable RLS
alter table public.trades enable row level security;

-- Policies

-- DROP existing policies if re-running to avoid conflicts
drop policy if exists "Users can insert their own trades" on public.trades;
drop policy if exists "Users can view their own trades" on public.trades;
drop policy if exists "Admins can view all trades" on public.trades;
drop policy if exists "Users and Admins can view trades" on public.trades;


-- Users can insert their own trades
-- Optimization: Wrap auth.uid() in (select ...) to prevent re-evaluation per row
create policy "Users can insert their own trades"
  on public.trades for insert
  with check ( (select auth.uid()) = user_id );

-- Unified SELECT policy
-- optimizations:
-- 1. Combine User and Admin policies to avoid "Multiple Permissive Policies" warning
-- 2. Use (select ...) for auth functions to optimize query plan
create policy "Users and Admins can view trades"
  on public.trades for select
  using (
    (select auth.uid()) = user_id
    or
    (select public.is_admin())
  );
