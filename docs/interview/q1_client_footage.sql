-- Interview question: "Do clients film their own footage?"
-- YES: tracks when footage was asked for, when it is due and when it came in.
--      (The "20 - Awaiting Footage" stage is already on the board.)
-- NO:  skip this file.

alter table public.creatives
  add column footage_requested_at timestamptz,
  add column footage_due_date     date,
  add column footage_received_at  timestamptz;
