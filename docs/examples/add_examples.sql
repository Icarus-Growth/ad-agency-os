-- =============================================================================
-- Example rows. Every row here is fake and has is_example = true.
-- Remove them all with docs/examples/delete_examples.sql.
-- Example people cannot sign in (can_sign_in = false).
-- =============================================================================

insert into public.team (id, full_name, email, job_title, access, can_sign_in, capacity, is_example) values
  ('aaaaaaaa-0000-4000-8000-000000000001', 'Alex Example',  'alex@example.com',  'Account Manager', 'Member', false, 8, true),
  ('aaaaaaaa-0000-4000-8000-000000000002', 'Sam Example',   'sam@example.com',   'Specialist',      'Member', false, 6, true),
  ('aaaaaaaa-0000-4000-8000-000000000003', 'Jordan Example','jordan@example.com','Specialist',      'Member', false, 2, true);

insert into public.clients (id, client_name, status, website, contact_name, contact_email, start_date,
                            onboarding_stage, account_manager_id, notes, is_example) values
  ('cccccccc-0000-4000-8000-000000000001', 'Example Client A', 'Active', 'https://example.com', 'Pat Example', 'pat@example.com',
   current_date - 60, '100 - Onboarded', 'aaaaaaaa-0000-4000-8000-000000000001', 'Example row.', true),
  ('cccccccc-0000-4000-8000-000000000002', 'Example Client B', 'Active', 'https://example.org', 'Lee Example', 'lee@example.org',
   current_date - 20, '50 - Call Taken', 'aaaaaaaa-0000-4000-8000-000000000001', 'Example row.', true),
  ('cccccccc-0000-4000-8000-000000000003', 'Example Client C', 'Active', 'https://example.net', 'Kim Example', 'kim@example.net',
   current_date - 2, '10 - Contract Sent', 'aaaaaaaa-0000-4000-8000-000000000002', 'Example row.', true);

-- Onboarding that has not moved for a while, so the dashboard has something to show.
update public.clients set onboarding_stage_changed_at = now() - interval '9 days'
where id = 'cccccccc-0000-4000-8000-000000000002';

insert into public.tasks (task_name, client_id, stage, assignee_id, due_date, is_example) values
  ('Example: send the welcome pack',        'cccccccc-0000-4000-8000-000000000003', '10 - In Progress', 'aaaaaaaa-0000-4000-8000-000000000001', current_date + 1, true),
  ('Example: book the onboarding call',     'cccccccc-0000-4000-8000-000000000002', '9 - Blocked',      'aaaaaaaa-0000-4000-8000-000000000001', current_date - 2, true),
  ('Example: tidy the shared drive',        null,                                   '0 - Backlog',      'aaaaaaaa-0000-4000-8000-000000000003', null,             true),
  ('Example: monthly check-in notes',       'cccccccc-0000-4000-8000-000000000001', '30 - In Review',   'aaaaaaaa-0000-4000-8000-000000000002', current_date,     true);

insert into public.calls (client_id, title, call_type, call_at, summary, action_items, is_example) values
  ('cccccccc-0000-4000-8000-000000000001', 'Example: monthly check-in', 'Check-In',   now() - interval '7 days',
   'Example summary. The client is happy with the results so far.', 'Send the next month''s plan.', true),
  ('cccccccc-0000-4000-8000-000000000002', 'Example: onboarding call',  'Onboarding', now() - interval '3 days',
   'Example summary. Access was given during the call.', 'Start the first piece of work.', true),
  ('cccccccc-0000-4000-8000-000000000003', 'Example: sales call',       'Sales',      now() - interval '10 days',
   'Example summary. The client signed up after the call.', 'Send the contract.', true);

insert into public.onboarding_forms (client_id, submitted_by_name, submitted_by_email, company_name, answers, is_example) values
  ('cccccccc-0000-4000-8000-000000000002', 'Lee Example', 'lee@example.org', 'Example Client B',
   '{"what_do_you_sell": "Example answer.", "who_do_you_sell_to": "Example answer."}'::jsonb, true);

update public.clients set form_received_at = now() - interval '4 days'
where id = 'cccccccc-0000-4000-8000-000000000002';

-- Ads examples ------------------------------------------------------------------
update public.clients set media_buyer_id = 'aaaaaaaa-0000-4000-8000-000000000002',
       editor_id = 'aaaaaaaa-0000-4000-8000-000000000003', market = 'Example market', ad_platform = 'Example platform'
where is_example;

insert into public.creatives (creative_name, client_id, stage, assignee_id, reviewer_id, angle, due_date, is_example) values
  ('Example: testimonial video',   'cccccccc-0000-4000-8000-000000000001', '100 - Launched',      'aaaaaaaa-0000-4000-8000-000000000003', 'aaaaaaaa-0000-4000-8000-000000000001', 'Example angle', current_date - 12, true),
  ('Example: problem and answer',  'cccccccc-0000-4000-8000-000000000001', '40 - Internal Review','aaaaaaaa-0000-4000-8000-000000000001', 'aaaaaaaa-0000-4000-8000-000000000001', 'Example angle', current_date,      true),
  ('Example: behind the scenes',   'cccccccc-0000-4000-8000-000000000002', '39 - Redo Requested', 'aaaaaaaa-0000-4000-8000-000000000003', 'aaaaaaaa-0000-4000-8000-000000000001', 'Example angle', current_date - 1,  true),
  ('Example: three quick tips',    'cccccccc-0000-4000-8000-000000000002', '20 - Awaiting Footage','aaaaaaaa-0000-4000-8000-000000000001', null,                                  'Example angle', current_date + 4,  true),
  ('Example: first script',        'cccccccc-0000-4000-8000-000000000003', '0 - To Script',       'aaaaaaaa-0000-4000-8000-000000000002', null,                                   null,            current_date + 6,  true);

insert into public.daily_metrics (client_id, metric_date, spend, leads, calls_booked, source, is_example) values
  ('cccccccc-0000-4000-8000-000000000001', current_date - 3, 100.00, 8, 2, 'Example platform', true),
  ('cccccccc-0000-4000-8000-000000000001', current_date - 2, 100.00, 5, 1, 'Example platform', true),
  ('cccccccc-0000-4000-8000-000000000001', current_date - 1, 100.00, 10, 3, 'Example platform', true);

insert into public.weekly_metrics (client_id, week_start, spend, leads, calls_booked, note, is_example) values
  ('cccccccc-0000-4000-8000-000000000001', date_trunc('week', current_date)::date - 7, 700.00, 46, 12, 'Example note.', true);

-- Example documents (0013, 0014): one on a card, one on a client page.
insert into public.documents (client_id, board, card_id, field_key, body_md, word_count, updated_by)
select c.client_id, 'creatives', c.id, 'script', d.body, coalesce(array_length(regexp_split_to_array(btrim(d.body), '\s+'), 1), 0), 'aaaaaaaa-0000-4000-8000-000000000001'
from public.creatives c, (values ($doc$# Problem and answer

**Hook:** Tired of ads that get clicks but no calls?

**Body:** Most ads stop at the click. Ours start there. We test one new angle every week and keep only what books calls.

**Call to action:** Book a free review today.$doc$)) d(body)
where c.creative_name = 'Example: problem and answer' and c.is_example;
