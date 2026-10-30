-- Interview question: "Do you set targets per client (cost per lead, leads per week)?"
-- YES: adds the targets to the client and a view that compares the last 7 days.
-- NO:  skip this file.

alter table public.clients
  add column target_cost_per_lead  numeric(12,2),
  add column target_leads_per_week int;

create view public.v_client_targets with (security_invoker = true) as
select c.id as client_id,
       c.client_name,
       c.target_cost_per_lead,
       c.target_leads_per_week,
       coalesce(sum(m.spend), 0) as spend_7d,
       coalesce(sum(m.leads), 0) as leads_7d,
       round(coalesce(sum(m.spend), 0) / nullif(sum(m.leads), 0), 2) as cost_per_lead_7d,
       (coalesce(sum(m.leads), 0) < c.target_leads_per_week
        or round(coalesce(sum(m.spend), 0) / nullif(sum(m.leads), 0), 2) > c.target_cost_per_lead) as off_target
from public.clients c
left join public.daily_metrics m on m.client_id = c.id and m.metric_date >= current_date - 7
where c.status = 'Active' and c.archived_at is null
group by c.id, c.client_name, c.target_cost_per_lead, c.target_leads_per_week;
comment on view public.v_client_targets is 'Last 7 days against each client''s targets.';
