---
name: editing-deadlines
description: Every day, posts the Editing pipeline cards that are late, due today or due in the next 2 days and not finished, grouped by the person who must act, with a link to each card. One post a day. Use when the user says "what is late in editing?", "editing deadlines", "which creatives are overdue?" or "post the deadlines now".
area: fulfilment
agency: ads
needs: [SUPABASE_URL, SUPABASE_SECRET_KEY, SLACK_BOT_TOKEN]
runs_on: modal
daily: true
---

# Editing deadlines

Tells the team, once a day, which ad creatives are late or due soon.
It only reads. It writes nothing to the database.

## What counts

- A card on the Editing pipeline board (`creatives`) with a due date.
- It is not finished. Only a `100 - ...` stage is finished.
- It is not archived.
- Its due date is before today (overdue), today, or in the next 2 days (due soon).

## What it posts

- One main post in `task-updates`: how many cards are overdue, due today and due soon,
  and a button that opens the board.
- One reply in the thread for each person (the card's assignee). Their cards are grouped
  as overdue, due today and due soon. Each line links to the card and gives the client,
  the stage and how late it is. People with a linked Slack account are tagged.
- Cards with nobody on them come last, under "Nobody is set to do these".
- Nothing is due: no post.
- It posts once a day at most.

A failure is posted once to `pipeline-errors`.

## Steps

1. The daily job runs it once a day. You do not need to start it.
2. To see what it would post (a dry run, the default):
   `python3 skills/fulfilment/editing-deadlines/scripts/editing_deadlines.py`
3. To post now: add `--now`.
4. To check as if it were another day: add `--today 2026-11-12`.

## Change it

`config.json`: how many days count as "due soon", the channel, and the most lines shown per
person.
