---
name: weekly-client-report
description: Once a week, sums last week's ad numbers for each active client into weekly_metrics and drafts the client's report (numbers, what went live, what is live, what the client must review). It posts each draft in the review channel for a person to check and send. It never sends to the client. Use when the user says "draft the weekly reports", "weekly client report", "what do we send clients this week?" or "sum last week's numbers".
area: fulfilment
agency: ads
needs: [SUPABASE_URL, SUPABASE_SECRET_KEY, SLACK_BOT_TOKEN]
runs_on: modal
daily: true
---

# Weekly client report

Writes last week's numbers and a report draft for each active client.
A person reads each draft and sends it. The skill never sends anything to a client.

## What it does

1. The daily job runs it every day. It does its work only on the report day (`weekday` in
   `config.json`, Monday by default). It does each client once per week.
2. The week is the last full week, Monday to Sunday.
3. It sums `daily_metrics` for that week: spend, leads and calls booked. It writes one row
   in `weekly_metrics` per client (`client_id` + `week_start`). A second run changes the
   same row. The database works out the cost per lead.
4. A client with no numbers for the week gets no row. Its draft says the numbers are not
   in yet. A missing number is never written as zero. A client with no numbers and nothing
   on the boards gets no draft (`skip_when_nothing_to_say` in `config.json`).
5. It reads the Editing pipeline board (`creatives`) and the Campaigns board
   (`ad_campaigns`): the ads and campaigns that went live in the week, the campaigns live
   now, and the cards that wait for the client's review. If the Campaigns board cannot be
   read, the draft leaves campaigns out and the result says "could not check".
6. It posts one draft per client in `review` (the `channel` in `config.json`), with the
   client link. The post tags the client's account manager.

A failure is posted once to `pipeline-errors`, with the client. The other clients go on.

## Steps for the person who sends it

1. Open the draft in `review`.
2. Check the numbers against the ad account.
3. Write the plan for next week where the draft says so.
4. Send it to the client yourself.

## Run it on demand

- See what it would write and post (a dry run, the default):
  `python3 skills/fulfilment/weekly-client-report/scripts/weekly_client_report.py`
- Write the numbers and post the drafts now, on any day:
  `python3 skills/fulfilment/weekly-client-report/scripts/weekly_client_report.py --now`
- Another week: add `--week-start 2026-11-02` (a Monday).

## Change it

`config.json`: the report day, the channel, the money label, the greeting and the
sign-off, and whether calls booked are shown.
