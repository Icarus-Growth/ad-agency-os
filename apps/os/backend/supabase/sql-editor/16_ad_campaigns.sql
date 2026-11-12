-- SQL editor paste 16 of 18: 0017_ad_campaigns.sql
-- Paste all of this into the Supabase SQL editor and press Run.
-- Wait for "Success" before you paste the next file.

-- =============================================================================
-- 0017  Ads: the Campaigns board (one card per ad campaign)
--
-- Boards on the Tasks screen are now: Tasks, Editing pipeline (the creatives
-- table) and Campaigns (the new ad_campaigns table).
--
--   * ad_campaigns: one ad campaign for one client, from backlog to ended.
--     Locked to the team, archived with its client, stage log on: the same
--     rules as every other board.
--   * creatives.ad_campaign_id: the campaign a creative runs in. Empty is fine.
--     Deleting a campaign leaves its creatives, with no campaign.
--     A creative may only join a campaign of its own client.
--   * brief_doc: the campaign brief opens in the app's editor (see 0013).
--     brief_doc_url stays: it is the "paste a link instead".
--   * The open cards view (the dashboard and My Work read it) has the new board.
--     Only "100 - Ended" is finished. "50 - Live" and "60 - Optimising" stay open.
-- =============================================================================

create type public.ad_campaign_stage as enum (
  '0 - Backlog',
  '10 - Planning',
  '20 - Building',
  '30 - Client Approval',
  '40 - Ready To Launch',
  '50 - Live',
  '60 - Optimising',
  '100 - Ended'
);

create table public.ad_campaigns (
  id                   uuid primary key default gen_random_uuid(),
  campaign_name        text not null,
  client_id            uuid not null references public.clients(id) on delete cascade,
  assignee_id          uuid references public.team(id) on delete set null,
  stage                public.ad_campaign_stage not null default '0 - Backlog',
  stage_changed_at     timestamptz,
  stage_changed_by_id  uuid references public.team(id) on delete set null,
  due_date             date,
  platform             text,
  objective            text,
  launch_date          date,
  end_date             date,
  brief_doc_url        text,
  results_notes        text,
  notes                text,
  position             int not null default 1,
  is_example           boolean not null default false,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
comment on table public.ad_campaigns is 'One ad campaign for one client. The "Campaigns" board.';
comment on column public.ad_campaigns.assignee_id is 'Who must act now: usually the media buyer.';
comment on column public.ad_campaigns.platform is 'Where the campaign runs, as a value (for example the platform name).';
comment on column public.ad_campaigns.objective is 'What the campaign is for, in a few words (for example leads or sales).';
comment on column public.ad_campaigns.brief_doc_url is 'A link to the brief, if it is kept outside the OS. The brief itself is the "brief_doc" document.';
comment on column public.ad_campaigns.results_notes is 'What the campaign got, in plain words. The numbers are in the report tables.';
comment on column public.ad_campaigns.position is 'The order of the card inside its stage. Lower comes first.';
create index ad_campaigns_client_idx on public.ad_campaigns (client_id);
create index ad_campaigns_assignee_idx on public.ad_campaigns (assignee_id);

create trigger ad_campaigns_touch_updated_at before update on public.ad_campaigns
  for each row execute function public.touch_updated_at();
select public.attach_stage_log('ad_campaigns');
-- Team only; archived_at and its guard (0010); the delete guard on clients (0016).
select public.lock_table('ad_campaigns');

-- The campaign a creative runs in ------------------------------------------------
comment on table public.creatives is 'One ad creative, from script to launched. The "Editing pipeline" board.';
alter table public.creatives
  add column ad_campaign_id uuid references public.ad_campaigns(id) on delete set null;
comment on column public.creatives.ad_campaign_id is 'The ad campaign this creative runs in. Empty is fine. Must be a campaign of the same client.';
create index creatives_ad_campaign_idx on public.creatives (ad_campaign_id);

create or replace function public.creative_campaign_same_client() returns trigger
language plpgsql set search_path = public as $fn$
begin
  if new.ad_campaign_id is not null and not exists (
    select 1 from public.ad_campaigns a where a.id = new.ad_campaign_id and a.client_id = new.client_id
  ) then
    raise exception 'That campaign belongs to another client. Pick a campaign of this creative''s client.'
      using errcode = '23514';
  end if;
  return new;
end
$fn$;
create trigger creatives_campaign_same_client before insert or update of ad_campaign_id, client_id on public.creatives
  for each row execute function public.creative_campaign_same_client();

-- A campaign cannot move to another client while creatives of the old client run in it.
create or replace function public.ad_campaign_keeps_client() returns trigger
language plpgsql set search_path = public as $fn$
begin
  if new.client_id is distinct from old.client_id and exists (
    select 1 from public.creatives c where c.ad_campaign_id = new.id and c.client_id <> new.client_id
  ) then
    raise exception 'Creatives of the old client run in this campaign. Take them out of it first.'
      using errcode = '23514';
  end if;
  return new;
end
$fn$;
create trigger ad_campaigns_keeps_client before update of client_id on public.ad_campaigns
  for each row execute function public.ad_campaign_keeps_client();

-- The brief is a document (0013) -------------------------------------------------
insert into public.document_fields (board, field_key, label, link_column) values
  ('ad_campaigns', 'brief_doc', 'Brief', 'brief_doc_url')
on conflict on constraint document_fields_key do update
  set label = excluded.label, link_column = excluded.link_column;

-- Every open card on every board, in one shape (as in 0011, plus Campaigns).
-- The creatives board is now called "Editing pipeline".
create or replace view public.v_open_cards with (security_invoker = true) as
select 'tasks'::text as board, 'Tasks'::text as board_label, id as card_id, task_name as card_name,
       client_id, stage::text as stage, split_part(stage::text, ' ', 1)::int as stage_number,
       assignee_id, reviewer_id, due_date, coalesce(stage_changed_at, created_at) as stage_changed_at, is_example
from public.tasks x where (stage not in ('100 - Complete', '-1 - Rejected'))
  and x.archived_at is null
  and not exists (select 1 from public.clients cl where cl.id = x.client_id and cl.archived_at is not null)
union all
select 'creatives', 'Editing pipeline', id, creative_name,
       client_id, stage::text, split_part(stage::text, ' ', 1)::int,
       assignee_id, reviewer_id, due_date, coalesce(stage_changed_at, created_at), is_example
from public.creatives x where (stage <> '100 - Launched')
  and x.archived_at is null
  and not exists (select 1 from public.clients cl where cl.id = x.client_id and cl.archived_at is not null)
union all
select 'ad_campaigns', 'Campaigns', id, campaign_name,
       client_id, stage::text, split_part(stage::text, ' ', 1)::int,
       assignee_id, null::uuid, due_date, coalesce(stage_changed_at, created_at), is_example
from public.ad_campaigns x where (stage <> '100 - Ended')
  and x.archived_at is null
  and not exists (select 1 from public.clients cl where cl.id = x.client_id and cl.archived_at is not null);
comment on view public.v_open_cards is 'Every open card on every board, in one shape. Finished and archived cards, and the cards of archived clients, are left out.';
