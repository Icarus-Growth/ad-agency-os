---
name: cost-per-lead-drift
description: Checks each active client's cost per lead every day. It compares the last 7 days with the client's own normal cost (or its target) and posts one alert per client that costs too much now, with the numbers and the client link. Use when the user says "check cost per lead", "which clients cost too much per lead?", "is any ad account drifting?" or "run the cost per lead alert now".
area: fulfilment
agency: ads
needs: [SUPABASE_URL, SUPABASE_SECRET_KEY, SLACK_BOT_TOKEN]
runs_on: modal
daily: true
---

# Cost per lead drift

Finds the clients whose cost per lead went up, and tells the team once a day.
It only reads. It writes nothing to the database.
It never posts in a client's channel.

## What it checks

- It reads `daily_metrics` (spend and leads per client per day).
- "Now" is the last 7 full days. Today is left out, because its numbers are not complete.
- "Normal" is the 28 days before that. If the client has a target cost per lead
  (`clients.target_cost_per_lead`), the target is used.
- A client drifts when its cost per lead now is 25% or more above normal.
- Spend with no leads at all is drift when the spend is more than one normal lead costs.
- A day with no row is not a zero. A client with too few days of numbers is skipped, and
  the result says why.
- Only clients with the status Active are checked. Archived clients are left out.

All these numbers are in `config.json`. Change them there.

## What it posts

One post per drifting client, once a day at most, in `needs-a-person` (the `channel` in
`config.json`). The post gives the cost per lead now, the normal cost, how much higher it
is, and who checks it (the client's media buyer, else its account manager). The button
opens the client in the OS.

A failure is posted once to `pipeline-errors`, with the client. The other clients are
still checked.

## Steps

1. The daily job runs it once a day. You do not need to start it.
2. To see what it would post, run a dry run. It posts nothing:
   `python3 skills/fulfilment/cost-per-lead-drift/scripts/cost_per_lead_drift.py`
3. To post the alerts now, run:
   `python3 skills/fulfilment/cost-per-lead-drift/scripts/cost_per_lead_drift.py --now`
4. To check a past day, add `--today 2026-11-03`.
5. Read the result. `drifting` lists the clients that cost too much. `skipped` lists the
   clients it could not judge, and why.
6. If a client is skipped for "not enough history", check that its ad numbers reach
   `daily_metrics`.
