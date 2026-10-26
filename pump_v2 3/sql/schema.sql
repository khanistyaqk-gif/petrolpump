-- Petrol Pump v2 core schema. Run ONCE in Supabase → SQL Editor on a NEW project.
-- (If you already have the old app's tables, do NOT run this; use Diagnostics → Schema check instead.)
-- Safe to re-run: every statement uses IF NOT EXISTS.

create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  name        text not null,
  role        text not null check (role in ('owner','manager','salesman')),
  phone       text,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now()
);

create table if not exists public.shifts (
  id          bigint generated always as identity primary key,
  salesman_id uuid not null references public.profiles(id),
  started_by  uuid references public.profiles(id),
  is_active   boolean not null default true,
  started_at  timestamptz not null default now(),
  ended_at    timestamptz,
  date        date not null default ((now() at time zone 'Asia/Kolkata')::date),
  created_at  timestamptz not null default now()
);
-- one active duty per salesman, enforced by the database
create unique index if not exists shifts_one_active_per_salesman
  on public.shifts (salesman_id) where is_active;

create table if not exists public.nozzles (
  id              bigint generated always as identity primary key,
  nozzle_name     text not null,
  fuel_type       text not null check (fuel_type in ('petrol','diesel','premium_petrol','premium_diesel')),
  current_reading numeric(14,3) not null default 0,
  is_active       boolean not null default true,
  created_by      uuid references public.profiles(id),
  created_at      timestamptz not null default now()
);

create table if not exists public.fuel_rates (
  id              bigint generated always as identity primary key,
  fuel_type       text not null check (fuel_type in ('petrol','diesel','premium_petrol','premium_diesel')),
  price_per_liter numeric(10,2) not null check (price_per_liter > 0),
  effective_from  date not null,
  created_by      uuid references public.profiles(id),
  created_at      timestamptz not null default now()
);

create table if not exists public.shift_assignments (
  id              bigint generated always as identity primary key,
  shift_id        bigint not null references public.shifts(id),
  salesman_id     uuid not null references public.profiles(id),
  nozzle_id       bigint not null references public.nozzles(id),
  opening_reading numeric(14,3) not null default 0,
  is_active       boolean not null default true,
  assigned_by     uuid references public.profiles(id),
  created_at      timestamptz not null default now(),
  ended_at        timestamptz
);
-- a nozzle can be active on only one duty at a time
create unique index if not exists assignments_one_active_per_nozzle
  on public.shift_assignments (nozzle_id) where is_active;

create table if not exists public.sale_entries (
  id              bigint generated always as identity primary key,
  shift_id        bigint not null references public.shifts(id),
  nozzle_id       bigint not null references public.nozzles(id),
  salesman_id     uuid not null references public.profiles(id),
  date            date not null,
  entry_time      timestamptz not null default now(),
  fuel_type       text not null,
  liters          numeric(14,2) not null check (liters > 0),
  rate            numeric(10,2) not null,
  locked_rate     numeric(10,2),
  rate_date       date,
  rate_snapshot   jsonb,
  amount          numeric(14,2) not null,
  payment_mode    text,
  credit_party_id bigint,
  vehicle_number  text,
  status          text not null default 'pending'
                  check (status in ('pending','approved','rejected','cancelled')),
  approved_by     uuid references public.profiles(id),
  created_at      timestamptz not null default now()
);
create index if not exists sale_entries_shift_idx on public.sale_entries (shift_id);

create table if not exists public.settlements (
  id                            bigint generated always as identity primary key,
  shift_id                      bigint not null unique references public.shifts(id),
  salesman_id                   uuid not null references public.profiles(id),
  date                          date not null,
  nozzle_readings               jsonb not null default '[]'::jsonb,
  meter_total                   numeric(14,2) not null default 0,
  entries_total                 numeric(14,2) not null default 0,
  difference                    numeric(14,2) not null default 0,
  cash_amount                   numeric(14,2) not null default 0,
  paytm_amount                  numeric(14,2) not null default 0,
  ccms_amount                   numeric(14,2) not null default 0,
  credit_amount                 numeric(14,2) not null default 0,
  cash_given_to_creditor_amount numeric(14,2) not null default 0,
  cash_transfer_expected        numeric(14,2) not null default 0,
  status                        text not null default 'pending'
                                check (status in ('pending','hold','approved','rejected')),
  manager_note                  text,
  created_at                    timestamptz not null default now(),
  approved_by                   uuid references public.profiles(id),
  approved_at                   timestamptz
);

-- Lock every table to the server (service) key. The public anon key then reads nothing.
do $$
declare t text;
begin
  foreach t in array array['profiles','shifts','nozzles','fuel_rates','shift_assignments','sale_entries','settlements']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
