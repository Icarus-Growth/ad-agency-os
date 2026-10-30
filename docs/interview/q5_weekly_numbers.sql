-- Interview question: "Which numbers do you report?"
-- The basic numbers are already there: spend, leads, cost per lead, calls booked.
-- For each EXTRA number the agency owner names, keep its two lines below and delete
-- the rest. If none, skip this file.

alter table public.daily_metrics  add column if not exists impressions int not null default 0;
alter table public.weekly_metrics add column if not exists impressions int not null default 0;

alter table public.daily_metrics  add column if not exists link_clicks int not null default 0;
alter table public.weekly_metrics add column if not exists link_clicks int not null default 0;

alter table public.daily_metrics  add column if not exists calls_showed int not null default 0;
alter table public.weekly_metrics add column if not exists calls_showed int not null default 0;

alter table public.daily_metrics  add column if not exists sales int not null default 0;
alter table public.weekly_metrics add column if not exists sales int not null default 0;
