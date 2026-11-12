"""editing-deadlines, offline, on fake example data.

    python3 -m pytest skills/fulfilment/editing-deadlines -q
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    _kit = [k for k in (_up / "skills/_kit", _up / "core/skills/_kit") if (k / "skillkit.py").exists()]
    if _kit:
        sys.path.insert(0, str(_kit[0]))
        break
import skill_fakes as fakes  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, str(SKILL / "scripts" / file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ed = _load("editing_deadlines_under_test", "editing_deadlines.py")
daily = _load("editing_deadlines_daily_under_test", "daily.py")

TODAY = date(2026, 11, 11)


def card(cid, name, due, stage="30 - To Edit", who="t-sam", **kw):
    return dict({"id": cid, "creative_name": name, "client_id": "c-acme", "stage": stage, "due_date": due,
                 "assignee_id": who}, **kw)


def make_db() -> fakes.FakeDB:
    return fakes.FakeDB({
        "settings": [{"id": 1, "os_url": "https://os.example.com"}],
        "team": [{"id": "t-sam", "full_name": "Sam Lee", "slack_user_id": "member-sam"},
                 {"id": "t-jane", "full_name": "Jane Doe"}],
        "clients": [{"id": "c-acme", "client_name": "Acme Dental"}],
        "creatives": [
            card("cr-late", "Before and after", "2026-11-08"),
            card("cr-today", "Price hook", "2026-11-11", stage="10 - Script Review", who="t-jane"),
            card("cr-soon", "Team intro", "2026-11-13"),
            card("cr-later", "Holiday offer", "2026-11-20"),                     # too far out
            card("cr-done", "Launched ad", "2026-11-01", stage="100 - Launched"),  # finished
            card("cr-arch", "Old card", "2026-11-02", archived_at="2026-11-05T10:00:00Z"),
            card("cr-free", "Nobody yet", "2026-11-10", who=None),
            card("cr-nodate", "No date", None),
        ],
    })


def test_one_post_with_a_thread_per_person_and_card_links():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    out = daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)
    assert out["ok"] and out["posted"] and out["cards"] == 4
    assert (out["Overdue"], out["Due today"], out["Due soon"]) == (2, 1, 1)

    main, *replies = slack.posts
    assert main["channel"] == "chan-task-updates" and main["thread_ts"] is None
    assert "2 overdue, 1 due today, 1 due in the next 2 days" in main["text"]
    assert main["blocks"][1]["elements"][0]["url"] == "https://os.example.com/tasks/creatives"
    assert all(r["thread_ts"] == "ts-1" for r in replies)
    assert [r["text"].splitlines()[0] for r in replies] == ["*Jane Doe*", "*Sam Lee (<@member-sam>)*",
                                                            "*Nobody is set to do these*"]
    sam = replies[1]["text"]
    assert "<https://os.example.com/board/creatives/cr-late|Before and after> (Acme Dental), 30 - To Edit, 3 days late" in sam
    assert "Team intro" in sam and "due Fri 13 Nov" in sam
    for gone in ("Holiday offer", "Launched ad", "Old card", "No date"):
        assert all(gone not in p["text"] for p in slack.posts)
    assert db.writes == []


def test_only_one_post_a_day_and_none_when_nothing_is_due():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)
    n = len(slack.posts)
    assert daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)["skipped"] == "already posted today"
    assert len(slack.posts) == n

    empty = fakes.FakeDB({"creatives": [card("x", "Far away", "2026-12-30")]})
    slack2 = fakes.FakeSlack()
    assert daily.run(empty, slack2, fakes.FakeConfig(), {}, TODAY)["posted"] is False
    assert slack2.posts == []


def test_board_that_cannot_be_read_is_one_clean_failure():
    db = make_db()
    db.fail_on["creatives"] = RuntimeError("permission denied")
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, TODAY)
    assert out["ok"] is False
    assert [p["channel"] for p in slack.posts] == ["chan-pipeline-errors"]
    assert db.writes == []


def test_bad_config_stops_with_a_plain_message(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text('{"due_soon_days": "two"}')
    try:
        ed.load_config(bad)
    except ValueError as e:
        assert "whole number of days" in str(e)
    else:
        raise AssertionError("a bad number of days should stop the run")
