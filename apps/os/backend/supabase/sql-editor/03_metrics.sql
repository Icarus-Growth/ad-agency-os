-- SQL editor paste 3 of 15: 0003_metrics.sql
-- Paste all of this into the Supabase SQL editor and press Run.
-- Wait for "Success" before you paste the next file.

-- =============================================================================
-- 0003  Report numbers: ads
--
-- daily_metrics:  one client on one day.
-- weekly_metrics: one client in one week (week_start is a Monday).
-- They stay empty until you connect your ad platform. The platform is a value
-- in the "source" column, never a column name.
-- Cost per lead is worked out by the database from spend and leads.
-- =============================================================================

create table public.daily_metrics (
  id              uuid primary key default gen_random_uuid(),
  client_id       uuid not null references public.clients(id) on delete cascade,
  metric_date     date not null,
  spend           numeric(12,2) not null default 0,
  leads           int not null default 0,
  calls_booked    int not null default 0,
  cost_per_lead   numeric generated always as (round(spend / nullif(leads, 0), 2)) stored,
  source          text,
  is_example      boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (client_id, metric_date)
);
comment on table public.daily_metrics is 'One client on one day. Ad numbers.';

create table public.weekly_metrics (
  id              uuid primary key default gen_random_uuid(),
  client_id       uuid not null references public.clients(id) on delete cascade,
  week_start      date not null,
  spend           numeric(12,2) not null default 0,
  leads           int not null default 0,
  calls_booked    int not null default 0,
  cost_per_lead   numeric generated always as (round(spend / nullif(leads, 0), 2)) stored,
  note            text,
  is_example      boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (client_id, week_start)
);
comment on table public.weekly_metrics is 'One client in one week. The daily numbers summed, plus a short note.';

create trigger daily_metrics_touch_updated_at before update on public.daily_metrics
  for each row execute function public.touch_updated_at();
create trigger weekly_metrics_touch_updated_at before update on public.weekly_metrics
  for each row execute function public.touch_updated_at();
