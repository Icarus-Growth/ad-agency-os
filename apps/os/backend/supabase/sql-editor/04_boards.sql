-- SQL editor paste 4 of 18: 0004_boards.sql
-- Paste all of this into the Supabase SQL editor and press Run.
-- Wait for "Success" before you paste the next file.

-- =============================================================================
-- 0004  Boards: ads (done-for-you)
--
-- Boards on the Tasks screen: Tasks (made in 0001) and Creatives.
-- One creative card goes from script to launched. "100 - Launched" is the last
-- stage, so there is no separate launches table.
-- =============================================================================

-- Ads columns on the client (wide-table rule) --------------------------------
alter table public.clients
  add column media_buyer_id      uuid references public.team(id) on delete set null,
  add column editor_id           uuid references public.team(id) on delete set null,
  add column market              text,
  add column ad_platform         text,
  add column ad_account_id       text,
  add column ad_account_access   boolean not null default false,
  add column monthly_ad_budget   numeric(12,2),
  add column lead_sheet_url      text,
  add column footage_folder_url  text;
comment on column public.clients.ad_platform is 'Where the ads run, as a value (for example the platform name).';
comment on column public.clients.ad_account_id is 'The ad account number. Never a login or a token.';
comment on column public.clients.ad_account_access is 'Ticked when the agency has access to the client''s ad account.';

-- Creatives board ------------------------------------------------------------
create type public.creative_stage as enum (
  '0 - To Script',
  '10 - Script Review',
  '19 - Script Changes',
  '20 - Awaiting Footage',
  '30 - To Edit',
  '39 - Redo Requested',
  '40 - Internal Review',
  '49 - Client Changes',
  '50 - Client Review',
  '60 - Ready To Launch',
  '100 - Launched'
);
create type public.creative_format as enum ('Video');

create table public.creatives (
  id                   uuid primary key default gen_random_uuid(),
  creative_name        text not null,
  client_id            uuid not null references public.clients(id) on delete cascade,
  stage                public.creative_stage not null default '0 - To Script',
  stage_changed_at     timestamptz,
  stage_changed_by_id  uuid references public.team(id) on delete set null,
  format               public.creative_format not null default 'Video',
  assignee_id          uuid references public.team(id) on delete set null,
  reviewer_id          uuid references public.team(id) on delete set null,
  angle                text,
  hook                 text,
  script_url           text,
  script_text          text,
  raw_footage_url      text,
  edited_url           text,
  feedback_notes       text,
  due_date             date,
  launch_date          date,
  ad_id                text,
  notes                text,
  is_example           boolean not null default false,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
comment on table public.creatives is 'One ad creative, from script to launched. The "Creatives" board.';
comment on column public.creatives.assignee_id is 'Who must act now: the script writer, then the editor.';
comment on column public.creatives.launch_date is 'Filled by the database when the card reaches 100 - Launched.';
create index creatives_client_idx on public.creatives (client_id);
create index creatives_assignee_idx on public.creatives (assignee_id);

-- Fill the launch date when a card reaches "100 - Launched".
create or replace function public.fill_launch_date() returns trigger
language plpgsql as $fn$
begin
  if new.stage = '100 - Launched' and new.launch_date is null then
    new.launch_date := current_date;
  end if;
  return new;
end
$fn$;
create trigger creatives_fill_launch_date before insert or update of stage on public.creatives
  for each row execute function public.fill_launch_date();

create trigger creatives_touch_updated_at before update on public.creatives
  for each row execute function public.touch_updated_at();
select public.attach_stage_log('creatives');

-- Every open card on every board, in one shape. The dashboard reads this.
create view public.v_open_cards with (security_invoker = true) as
select 'tasks'::text as board, 'Tasks'::text as board_label, id as card_id, task_name as card_name,
       client_id, stage::text as stage, split_part(stage::text, ' ', 1)::int as stage_number,
       assignee_id, reviewer_id, due_date, coalesce(stage_changed_at, created_at) as stage_changed_at, is_example
from public.tasks where stage not in ('100 - Complete', '-1 - Rejected')
union all
select 'creatives', 'Creatives', id, creative_name,
       client_id, stage::text, split_part(stage::text, ' ', 1)::int,
       assignee_id, reviewer_id, due_date, coalesce(stage_changed_at, created_at), is_example
from public.creatives where stage <> '100 - Launched';
comment on view public.v_open_cards is 'Every open card on every board, in one shape. Finished cards are left out.';
