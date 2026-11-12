"""weekly-client-report, offline, on fake example data.

    python3 -m pytest skills/fulfilment/weekly-client-report -q
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    _kit = [k for k in (_up / "skills/_kit", _up / "core/skills/_kit") if (k / "skillkit.py").exists()]
    if _kit:
        sys.path.insert(0, str(_kit[0]))
        break
import skill_fakes as fakes  # noqa: E402
import skillkit  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, str(SKILL / "scripts" / file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wcr = _load("weekly_report_under_test", "weekly_client_report.py")
daily = _load("weekly_report_daily_under_test", "daily.py")

MONDAY = date(2026, 11, 9)
WEEK = date(2026, 11, 2)       # the week reported: 2 to 8 Nov
PREV = date(2026, 10, 26)
ACME, BRIGHT = "c-acme", "c-bright"


def day_rows(client_id, start, spend, leads, calls, days=7):
    return [{"id": "{0}-{1}".format(client_id, (start + timedelta(days=i)).isoformat()), "client_id": client_id,
             "metric_date": (start + timedelta(days=i)).isoformat(), "spend": spend, "leads": leads,
             "calls_booked": calls} for i in range(days)]


def make_db() -> fakes.FakeDB:
    return fakes.FakeDB({
        "settings": [{"id": 1, "os_url": "https://os.example.com"}],
        "team": [{"id": "t-jane", "full_name": "Jane Doe", "status": "Active", "slack_user_id": "member-jane"}],
        "clients": [
            {"id": ACME, "client_name": "Acme Dental", "status": "Active", "contact_name": "Sam Lee",
             "account_manager_id": "t-jane", "slack_channel_id": "client-channel-acme"},
            {"id": BRIGHT, "client_name": "Bright Smiles", "status": "Active"},
        ],
        "daily_metrics": day_rows(ACME, WEEK, 300, 10, 2) + day_rows(ACME, PREV, 200, 10, 1),
        "weekly_metrics": [],
        "creatives": [
            {"id": "cr-1", "creative_name": "Before and after", "client_id": ACME, "stage": "100 - Launched",
             "launch_date": "2026-11-04", "ad_campaign_id": "camp-1"},
            {"id": "cr-2", "creative_name": "Price hook", "client_id": ACME, "stage": "50 - Client Review"},
            {"id": "cr-3", "creative_name": "Old ad", "client_id": ACME, "stage": "100 - Launched",
             "launch_date": "2026-10-01"},
        ],
        "ad_campaigns": [
            {"id": "camp-1", "campaign_name": "Spring offer", "client_id": ACME, "stage": "50 - Live",
             "launch_date": "2026-11-03"},
        ],
    })


def test_writes_the_week_and_posts_a_draft_for_review_only():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    out = daily.run(db, slack, fakes.FakeConfig(), seen, MONDAY)
    assert out["ok"] and out["week_start"] == "2026-11-02"

    rows = db.tables["weekly_metrics"]
    assert len(rows) == 1
    acme = rows[0]
    assert acme["client_id"] == ACME and acme["week_start"] == "2026-11-02"
    assert (acme["spend"], acme["leads"], acme["calls_booked"]) == (2100, 70, 14)
    assert "cost_per_lead" not in acme          # the database works it out
    assert out["no_numbers"] == ["Bright Smiles"]  # no rows: no zero row written

    assert out["nothing_to_say"] == ["Bright Smiles"]  # no numbers and no cards: no draft
    assert [p["channel"] for p in slack.posts] == ["chan-review"]
    assert all("client-channel" not in p["channel"] for p in slack.posts)
    acme_post = slack.posts[0]["text"]
    assert "NOT sent to the client" in acme_post and "<@member-jane>" in acme_post
    assert "Spend: 2,100.00 USD (the week before: 1,400.00 USD)" in acme_post
    assert "Cost per lead: 30.00 USD (the week before: 20.00 USD)" in acme_post
    assert "\"Spring offer\" went live on 3 Nov" in acme_post
    assert "Before and after (Spring offer)" in acme_post and "Old ad" not in acme_post
    assert "Please review \"Price hook\"" in acme_post
    assert slack.posts[0]["blocks"][1]["elements"][0]["url"] == "https://os.example.com/clients/c-acme"


def test_no_numbers_is_said_never_written_as_zero():
    db = make_db()
    db.tables["creatives"].append({"id": "cr-9", "creative_name": "Smile reveal", "client_id": BRIGHT,
                                   "stage": "50 - Client Review"})
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, MONDAY)
    assert out["no_numbers"] == ["Bright Smiles"]
    assert [r["client_id"] for r in db.tables["weekly_metrics"]] == [ACME]
    bright = slack.posts[1]["text"]
    assert "Bright Smiles" in bright and "could not get this week's ad numbers" in bright
    assert "Spend:" not in bright and "Please review \"Smile reveal\"" in bright


def test_runs_once_a_week_and_only_on_the_report_day():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    assert "skipped" in daily.run(db, slack, fakes.FakeConfig(), seen, MONDAY + timedelta(days=1))
    assert slack.posts == [] and db.writes == []
    daily.run(db, slack, fakes.FakeConfig(), seen, MONDAY)
    again = daily.run(db, slack, fakes.FakeConfig(), seen, MONDAY)
    assert again["posted"] == 0 and len(slack.posts) == 1
    assert len(db.tables["weekly_metrics"]) == 1  # upsert: the same row, not a second one


def test_missing_campaign_table_still_drafts():
    db = make_db()
    db.fail_on["ad_campaigns"] = RuntimeError("relation ad_campaigns does not exist")
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, MONDAY)
    assert out["ok"] and out["campaigns"].startswith("could not check")
    assert "Spring offer" not in slack.posts[0]["text"] and "Before and after" in slack.posts[0]["text"]


def test_bad_number_is_one_clean_failure_and_no_row_written():
    db = make_db()
    db.tables["daily_metrics"][0]["spend"] = "lots"
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, MONDAY)
    assert out["ok"] is False
    assert db.tables["weekly_metrics"] == []
    errors = [p for p in slack.posts if p["channel"] == "chan-pipeline-errors"]
    assert len(errors) == 1 and "Acme Dental" in errors[0]["text"]


def test_bad_weekday_in_config_stops_with_a_plain_message():
    cfg = dict(wcr.load_config(), weekday="Someday")
    db, slack = make_db(), fakes.FakeSlack()
    try:
        wcr.run(db, slack, fakes.FakeConfig(), {}, MONDAY, cfg=cfg)
    except ValueError as e:
        assert "must be a day name" in str(e)
    else:
        raise AssertionError("a bad weekday should stop the run")
    assert db.writes == [] and slack.posts == []


def test_week_start_must_be_a_monday(capsys):
    assert wcr.main(["--week-start", "2026-11-04"]) == 2
    assert "must be a Monday" in capsys.readouterr().out
