"""cost-per-lead-drift, offline, on fake example data.

    python3 -m pytest skills/fulfilment/cost-per-lead-drift -q
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


cpl = _load("cpl_drift_under_test", "cost_per_lead_drift.py")
daily = _load("cpl_drift_daily_under_test", "daily.py")

TODAY = date(2026, 11, 11)
ACME, BRIGHT, QUIET = "c-acme", "c-bright", "c-quiet"


def metrics(client_id: str, days: range, spend: float, leads: int):
    return [{"id": "{0}-{1}".format(client_id, d), "client_id": client_id,
             "metric_date": (TODAY - timedelta(days=d)).isoformat(), "spend": spend, "leads": leads}
            for d in days]


def make_db() -> fakes.FakeDB:
    rows = (
        # Acme Dental: 30 per lead for four weeks, then 60 per lead last week. Drift.
        metrics(ACME, range(8, 36), 300, 10) + metrics(ACME, range(1, 8), 300, 5)
        # Bright Smiles: steady at 30 per lead. No alert.
        + metrics(BRIGHT, range(1, 36), 300, 10)
        # Quiet Clinic: only three days of numbers. Not enough to judge.
        + metrics(QUIET, range(1, 4), 100, 1)
    )
    return fakes.FakeDB({
        "settings": [{"id": 1, "os_url": "https://os.example.com"}],
        "team": [{"id": "t-sam", "full_name": "Sam Lee", "status": "Active", "slack_user_id": "member-sam"}],
        "clients": [
            {"id": ACME, "client_name": "Acme Dental", "status": "Active", "media_buyer_id": "t-sam"},
            {"id": BRIGHT, "client_name": "Bright Smiles", "status": "Active"},
            {"id": QUIET, "client_name": "Quiet Clinic", "status": "Active"},
            {"id": "c-old", "client_name": "Old Client", "status": "Ended"},
        ],
        "daily_metrics": rows,
    })


def test_one_alert_for_the_drifting_client_with_numbers_and_link():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    out = daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)
    assert out["ok"] and out["drifting"] == ["Acme Dental"] and out["posted"] == 1
    assert len(slack.posts) == 1
    post = slack.posts[0]
    assert post["channel"] == "chan-needs-a-person"
    assert "Acme Dental" in post["text"] and "60.00 USD per lead" in post["text"]
    assert "30.00 USD per lead" in post["text"] and "100% higher" in post["text"]
    assert "<@member-sam>" in post["text"]
    assert post["blocks"][1]["elements"][0]["url"] == "https://os.example.com/clients/c-acme"
    assert any("Quiet Clinic" in s for s in out["skipped"])
    # It only reads: nothing was written to the database.
    assert db.writes == []


def test_second_run_the_same_day_posts_nothing_more():
    db, slack, seen = make_db(), fakes.FakeSlack(), {}
    daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)
    out = daily.run(db, slack, fakes.FakeConfig(), seen, TODAY)
    assert out["posted"] == 0 and len(slack.posts) == 1


def test_client_target_wins_over_history():
    db = make_db()
    db.tables["clients"][1]["target_cost_per_lead"] = 20  # Bright Smiles runs at 30, target 20
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, TODAY)
    assert sorted(out["drifting"]) == ["Acme Dental", "Bright Smiles"]
    assert any("The client's target: 20.00 USD" in p["text"] for p in slack.posts)


def test_spend_with_no_leads_is_drift():
    client = {"id": "x", "client_name": "Acme Dental"}
    rows = metrics("x", range(8, 36), 300, 10) + metrics("x", range(1, 8), 100, 0)
    r = cpl.check_client(client, rows, TODAY, cpl.load_config())
    assert r["status"] == "drift" and r["recent_cpl"] is None
    assert "spent and no leads" in cpl.message(r, "Sam Lee", cpl.load_config())


def test_bad_metric_row_is_one_clean_failure_and_nothing_written():
    db = make_db()
    db.tables["daily_metrics"].append({"id": "bad", "client_id": ACME,
                                       "metric_date": (TODAY - timedelta(days=2)).isoformat(),
                                       "spend": "not a number", "leads": 1})
    slack = fakes.FakeSlack()
    out = daily.run(db, slack, fakes.FakeConfig(), {}, TODAY)
    assert out["ok"] is False
    errors = [p for p in slack.posts if p["channel"] == "chan-pipeline-errors"]
    assert len(errors) == 1 and "Acme Dental" in errors[0]["text"]
    assert not [p for p in slack.posts if p["channel"] == "chan-needs-a-person"]
    assert db.writes == []


def test_missing_keys_stop_with_a_plain_message(monkeypatch, capsys):
    monkeypatch.setattr(skillkit, "load_dotenv", lambda *a, **k: None)
    for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SLACK_BOT_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    try:
        cpl.main(["--now"])
    except skillkit.MissingKey as e:
        assert "SUPABASE_URL" in str(e) and "SLACK_BOT_TOKEN" in str(e)
    else:
        raise AssertionError("it should stop when keys are missing")
