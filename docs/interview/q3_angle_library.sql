-- Interview question: "Do you test ad angles and keep the ones that work?"
-- YES: adds an angle library. Each creative can point at one angle.
-- NO:  skip this file. The free-text "angle" column on creatives is enough.

create table public.angle_library (
  id           uuid primary key default gen_random_uuid(),
  angle_name   text not null,
  market       text,
  angle_type   text,
  description  text,
  is_winner    boolean not null default false,
  is_example   boolean not null default false,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
comment on table public.angle_library is 'One ad angle. Many creatives can use the same angle.';
create trigger angle_library_touch_updated_at before update on public.angle_library
  for each row execute function public.touch_updated_at();
select public.lock_table('angle_library');

alter table public.creatives add column angle_id uuid references public.angle_library(id) on delete set null;
