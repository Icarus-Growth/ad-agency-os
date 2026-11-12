"""Cost per lead drift: one alert for each active client whose cost per lead went up.

It compares the last `recent_days` full days of daily_metrics with the client's own
baseline: the `baseline_days` days before that, or the client's target cost per lead
when the client has one (the clients.target_cost_per_lead column, if your OS has it).
A client that drifts gets one post a day at most, with the numbers and the client link.

The daily job runs it once a day (scripts/daily.py). On demand:

    python3 skills/fulfilment/cost-per-lead-drift/scripts/cost_per_lead_drift.py            (dry run)
    python3 skills/fulfilment/cost-per-lead-drift/scripts/cost_per_lead_drift.py --now      (posts)

A missing day is not a zero. The check counts only days that have a row.
It writes nothing to the database.
"""

from __future__ import annotations

import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    _kit = [k for k in (_up / "skills/_kit", _up / "core/skills/_kit") if (k / "skillkit.py").exists()]
    if _kit:
        sys.path.insert(0, str(_kit[0]))
        break
import skillkit  # noqa: E402

import argparse  # noqa: E402
import json  # noqa: E402
from datetime import date, timedelta  # noqa: E402
from typing import Any, Dict, List, MutableMapping, Optional  # noqa: E402

SKILL = "cost-per-lead-drift"
BOT = "📈 Cost Per Lead Alert"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "config.json"
DEFAULTS: Dict[str, Any] = {
    "recent_days": 7, "baseline_days": 28, "drift_percent": 25, "min_recent_days": 5,
    "min_baseline_days": 14, "min_baseline_leads": 5, "min_recent_spend": 0,
    "use_client_target": True, "channel": "needs-a-person", "currency": "USD",
}


def load_config(path: Path = CONFIG_FILE) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update({k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")})
    return cfg


def esc(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money(value: float, cfg: Dict[str, Any]) -> str:
    return "{0:,.2f} {1}".format(value, cfg.get("currency") or "").strip()


def windows(today: date, cfg: Dict[str, Any]) -> Dict[str, date]:
    """recent = [recent_start, today); baseline = [baseline_start, recent_start). Today is
    left out: its numbers are not complete yet."""
    recent_start = today - timedelta(days=int(cfg["recent_days"]))
    return {"recent_start": recent_start,
            "baseline_start": recent_start - timedelta(days=int(cfg["baseline_days"])),
            "end": today}


def _sum(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    return {"spend": sum(float(r.get("spend") or 0) for r in rows),
            "leads": sum(int(r.get("leads") or 0) for r in rows),
            "days": len({str(r.get("metric_date"))[:10] for r in rows})}


def check_client(client: Dict[str, Any], rows: List[Dict[str, Any]], today: date,
                 cfg: Dict[str, Any]) -> Dict[str, Any]:
    """The rule, pure. Returns status 'drift', 'ok' or 'skipped', with the numbers and why."""
    w = windows(today, cfg)
    recent, base = [], []
    for r in rows:
        d = str(r.get("metric_date") or "")[:10]
        if w["recent_start"].isoformat() <= d < w["end"].isoformat():
            recent.append(r)
        elif w["baseline_start"].isoformat() <= d < w["recent_start"].isoformat():
            base.append(r)
    now, before = _sum(recent), _sum(base)
    out: Dict[str, Any] = {"client_id": client.get("id"), "client_name": client.get("client_name") or "",
                           "recent": now, "baseline": before}

    target = client.get("target_cost_per_lead")
    if cfg.get("use_client_target") and target not in (None, "") and float(target) > 0:
        out["baseline_cpl"], out["baseline_kind"] = float(target), "target"
    elif before["days"] < int(cfg["min_baseline_days"]) or before["leads"] < int(cfg["min_baseline_leads"]):
        return dict(out, status="skipped", why="not enough history for a baseline ({0} days, {1} leads)".format(
            before["days"], before["leads"]))
    else:
        out["baseline_cpl"], out["baseline_kind"] = before["spend"] / before["leads"], "history"

    if now["days"] < int(cfg["min_recent_days"]):
        return dict(out, status="skipped", why="only {0} of the last {1} days have numbers".format(
            now["days"], cfg["recent_days"]))
    if now["spend"] <= float(cfg["min_recent_spend"]) or now["spend"] <= 0:
        return dict(out, status="skipped", why="no spend in the last {0} days".format(cfg["recent_days"]))

    if now["leads"] == 0:
        # No leads at all: drift when the spend is more than one normal lead costs.
        out["recent_cpl"], out["change_percent"] = None, None
        return dict(out, status="drift" if now["spend"] >= out["baseline_cpl"] else "ok")
    out["recent_cpl"] = now["spend"] / now["leads"]
    out["change_percent"] = (out["recent_cpl"] / out["baseline_cpl"] - 1) * 100
    return dict(out, status="drift" if out["change_percent"] >= float(cfg["drift_percent"]) else "ok")


def message(result: Dict[str, Any], who: str, cfg: Dict[str, Any]) -> str:
    now = result["recent"]
    lines = ["*Cost per lead is up for {0}.*".format(esc(result["client_name"]))]
    if result.get("recent_cpl") is None:
        lines.append("Last {0} days: {1} spent and no leads.".format(cfg["recent_days"], money(now["spend"], cfg)))
    else:
        lines.append("Last {0} days: {1} per lead ({2} spent, {3} leads).".format(
            cfg["recent_days"], money(result["recent_cpl"], cfg), money(now["spend"], cfg), now["leads"]))
    if result["baseline_kind"] == "target":
        lines.append("The client's target: {0} per lead.".format(money(result["baseline_cpl"], cfg)))
    else:
        lines.append("Its normal cost: {0} per lead (the {1} days before).".format(
            money(result["baseline_cpl"], cfg), cfg["baseline_days"]))
    if result.get("change_percent") is not None:
        lines.append("That is {0:.0f}% higher. The alert starts at {1}% higher.".format(
            result["change_percent"], cfg["drift_percent"]))
    lines.append("What to do: {0} checks the ads, the lead form and the tracking today.".format(who))
    return "\n".join(lines)


def _people(db: Any) -> Dict[str, Dict[str, Any]]:
    try:
        return {str(t["id"]): t for t in db.select_all("team", {"status": "eq.Active"}) or []}
    except Exception:  # noqa: BLE001 - a name is a nice-to-have
        return {}


def who_acts(client: Dict[str, Any], team: Dict[str, Dict[str, Any]]) -> str:
    for col in ("media_buyer_id", "account_manager_id"):
        p = team.get(str(client.get(col) or ""))
        if p:
            return "<@{0}>".format(p["slack_user_id"]) if p.get("slack_user_id") else esc(p.get("full_name"))
    return "The media buyer"


def run(db: Any, slack: Any, config: Any, seen: Optional[MutableMapping[str, Any]], today: date,
        cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Check every active client and post one alert per drifting client (once a day each)."""
    cfg = cfg or load_config()
    ctx = skillkit.Context(db, slack, config, seen)
    settings = ctx.settings()
    w = windows(today, cfg)
    clients = db.select_all("clients", {"status": "eq.Active", "archived_at": "is.null"}, order="client_name")
    by_client: Dict[str, List[Dict[str, Any]]] = {}
    for r in db.select_all("daily_metrics", {"metric_date": "gte." + w["baseline_start"].isoformat()},
                           order="metric_date") or []:
        by_client.setdefault(str(r.get("client_id")), []).append(r)
    team = _people(db)

    out: Dict[str, Any] = {"ok": True, "checked": 0, "drifting": [], "posted": 0, "skipped": []}
    for client in clients or []:
        link = skillkit.os_link(settings, "clients/{0}".format(client.get("id")))
        try:
            result = check_client(client, by_client.get(str(client.get("id")), []), today, cfg)
            out["checked"] += 1
            if result["status"] == "skipped":
                out["skipped"].append("{0}: {1}".format(result["client_name"], result["why"]))
                continue
            if result["status"] != "drift":
                continue
            out["drifting"].append(result["client_name"])
            key = "{0}:{1}:{2}".format(SKILL, client.get("id"), today.isoformat())
            if not skillkit.first_time(seen, key, hours=20):
                continue
            text = message(result, who_acts(client, team), cfg)
            if skillkit.post(ctx, cfg["channel"], BOT, text, link=link, button="Open the client"):
                out["posted"] += 1
        except Exception as e:  # noqa: BLE001 - one client must not stop the others
            out["ok"] = False
            skillkit.report_failure(ctx, SKILL, "check {0}".format(client.get("client_name")), e, link)
    return out


class DryRun:
    """Stands in for Slack and the channels: prints each post instead of sending it."""

    def channel_id(self, key: str) -> str:
        return "#" + key

    def post(self, channel: str, bot_name: str, text: str, blocks: Optional[list] = None,
             thread_ts: Optional[str] = None) -> str:
        print("--- would post in {0} as {1}:\n{2}\n".format(channel, bot_name, text))
        return "dry-run"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Alert on clients whose cost per lead went up.")
    ap.add_argument("--now", action="store_true", help="post the alerts now")
    ap.add_argument("--dry-run", action="store_true", help="print what it would post (the default)")
    ap.add_argument("--today", help="check as if today were this date (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    live = a.now and not a.dry_run
    ctx = skillkit.context(needs=["SLACK_BOT_TOKEN"] if live else [])
    today = date.fromisoformat(a.today) if a.today else date.today()
    if live:
        out = run(ctx.db, ctx.slack, ctx.config, {}, today)
    else:
        print("Dry run: nothing is posted. Add --now to post.\n")
        fake = DryRun()
        out = run(ctx.db, fake, fake, {}, today)
    print(skillkit.dump(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    skillkit.main_guard(main)
