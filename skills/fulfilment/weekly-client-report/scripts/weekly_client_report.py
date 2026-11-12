"""Weekly client report: sums last week into weekly_metrics and drafts each client's report.

Once a week (the `weekday` in config.json), for every active client:
  1. it sums last week's daily_metrics (Monday to Sunday) and writes one weekly_metrics row
     (upsert on client_id + week_start, so a second run changes the same row);
  2. it reads the creatives and ad_campaigns boards for what launched, what is live and
     what waits for the client;
  3. it drafts the report text and posts the draft in the review channel.

It never sends anything to the client. A person checks the draft and sends it.
The daily job runs it (scripts/daily.py); it does its work only on the report day, and
once per week per client. On demand:

    python3 skills/fulfilment/weekly-client-report/scripts/weekly_client_report.py          (dry run)
    python3 skills/fulfilment/weekly-client-report/scripts/weekly_client_report.py --now    (writes and posts)

A week with no numbers is never written as zero: the row is not written and the draft
says the numbers are not in yet.
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

SKILL = "weekly-client-report"
BOT = "📝 Weekly Report Draft"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "config.json"
DEFAULTS: Dict[str, Any] = {"weekday": "Monday", "channel": "review", "currency": "USD",
                            "show_calls_booked": True, "skip_when_nothing_to_say": True, "greeting": "Hi {name},",
                            "sign_off": "Thanks,\nThe team"}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
LIVE_CAMPAIGN = ("50 - Live", "60 - Optimising")
CAMPAIGN_WAITS_FOR_CLIENT = ("30 - Client Approval",)
CREATIVE_WAITS_FOR_CLIENT = ("50 - Client Review",)


def load_config(path: Path = CONFIG_FILE) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update({k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")})
    return cfg


def report_week(today: date) -> date:
    """The Monday of the last full week (Monday to Sunday) before today."""
    return today - timedelta(days=today.weekday() + 7)


def short_date(d: date) -> str:
    return "{0} {1}".format(d.day, d.strftime("%b"))


def money(value: float, cfg: Dict[str, Any]) -> str:
    return "{0:,.2f} {1}".format(value, cfg.get("currency") or "").strip()


def esc(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _day(value: Any) -> str:
    return str(value or "")[:10]


def in_week(value: Any, week_start: date) -> bool:
    d = _day(value)
    return bool(d) and week_start.isoformat() <= d <= (week_start + timedelta(days=6)).isoformat()


def sum_week(rows: List[Dict[str, Any]], week_start: date) -> Optional[Dict[str, Any]]:
    """Spend, leads and calls booked for one week. None when not one day has a row."""
    week = [r for r in rows if in_week(r.get("metric_date"), week_start)]
    if not week:
        return None
    return {"spend": round(sum(float(r.get("spend") or 0) for r in week), 2),
            "leads": sum(int(r.get("leads") or 0) for r in week),
            "calls_booked": sum(int(r.get("calls_booked") or 0) for r in week),
            "days": len({_day(r.get("metric_date")) for r in week})}


def _cpl(n: Optional[Dict[str, Any]]) -> Optional[float]:
    if not n or not n.get("leads"):
        return None
    return float(n["spend"]) / int(n["leads"])


def report_text(client: Dict[str, Any], week_start: date, now: Optional[Dict[str, Any]],
                before: Optional[Dict[str, Any]], boards: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    """The draft, as the client will read it. Plain text. Pure."""
    first = (client.get("contact_name") or "").split(" ")[0] or "team"
    week_end = week_start + timedelta(days=6)
    lines = [cfg["greeting"].format(name=first), "",
             "Here is your update for the week of {0} to {1}.".format(short_date(week_start), short_date(week_end)),
             ""]

    def was(key: str, fmt) -> str:
        if not before or before.get(key) is None:
            return ""
        return " (the week before: {0})".format(fmt(before[key]))

    if now is None:
        lines += ["The numbers", "- We could not get this week's ad numbers yet. We will send them when we have them."]
    else:
        lines += ["The numbers",
                  "- Spend: {0}{1}".format(money(now["spend"], cfg), was("spend", lambda v: money(v, cfg))),
                  "- Leads: {0}{1}".format(now["leads"], was("leads", str))]
        cpl, cpl_before = _cpl(now), _cpl(before)
        lines.append("- Cost per lead: {0}{1}".format(
            money(cpl, cfg) if cpl is not None else "no leads this week",
            " (the week before: {0})".format(money(cpl_before, cfg)) if cpl_before is not None else ""))
        if cfg.get("show_calls_booked"):
            lines.append("- Calls booked: {0}{1}".format(now["calls_booked"], was("calls_booked", str)))

    launched_campaigns = boards.get("campaigns_launched") or []
    launched_ads = boards.get("creatives_launched") or []
    if launched_campaigns or launched_ads:
        lines += ["", "What went live"]
        for c in launched_campaigns:
            lines.append("- The campaign \"{0}\" went live on {1}.".format(
                c.get("campaign_name"), short_date(date.fromisoformat(_day(c.get("launch_date"))))))
        if launched_ads:
            lines.append("- {0} new ad{1} launched: {2}.".format(
                len(launched_ads), "" if len(launched_ads) == 1 else "s",
                ", ".join(_ad_name(a, boards) for a in launched_ads)))

    live = boards.get("campaigns_live") or []
    if live:
        lines += ["", "Live now", "- {0} campaign{1}: {2}.".format(
            len(live), "" if len(live) == 1 else "s", ", ".join(c.get("campaign_name") or "" for c in live))]

    waiting = (boards.get("creatives_waiting") or []) + (boards.get("campaigns_waiting") or [])
    if waiting:
        lines += ["", "What we need from you"]
        for w in waiting:
            lines.append("- Please review \"{0}\".".format(w.get("creative_name") or w.get("campaign_name")))

    lines += ["", "Next week", "- (Write the plan for next week here.)", "", cfg["sign_off"]]
    return "\n".join(lines)


def _ad_name(ad: Dict[str, Any], boards: Dict[str, Any]) -> str:
    camp = (boards.get("campaign_names") or {}).get(str(ad.get("ad_campaign_id") or ""))
    return "{0} ({1})".format(ad.get("creative_name"), camp) if camp else str(ad.get("creative_name"))


def _read(db: Any, table: str, filters: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    """Rows, or None when the table cannot be read (for example ad_campaigns is not made yet)."""
    try:
        return db.select_all(table, filters) or []
    except Exception:  # noqa: BLE001 - a missing board is "could not check", never a failure
        return None


def boards_for(client_id: str, week_start: date, creatives: Optional[List[Dict[str, Any]]],
               campaigns: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    mine_ads = [c for c in creatives or [] if str(c.get("client_id")) == client_id]
    mine_camps = [c for c in campaigns or [] if str(c.get("client_id")) == client_id]
    return {
        "creatives_launched": [c for c in mine_ads if str(c.get("stage", "")).startswith("100 -")
                               and in_week(c.get("launch_date"), week_start)],
        "creatives_waiting": [c for c in mine_ads if c.get("stage") in CREATIVE_WAITS_FOR_CLIENT],
        "campaigns_launched": [c for c in mine_camps if in_week(c.get("launch_date"), week_start)],
        "campaigns_live": [c for c in mine_camps if c.get("stage") in LIVE_CAMPAIGN],
        "campaigns_waiting": [c for c in mine_camps if c.get("stage") in CAMPAIGN_WAITS_FOR_CLIENT],
        "campaign_names": {str(c.get("id")): c.get("campaign_name") for c in campaigns or []},
    }


def _people(db: Any) -> Dict[str, Dict[str, Any]]:
    try:
        return {str(t["id"]): t for t in db.select_all("team", {"status": "eq.Active"}) or []}
    except Exception:  # noqa: BLE001
        return {}


def _who(client: Dict[str, Any], team: Dict[str, Dict[str, Any]]) -> str:
    p = team.get(str(client.get("account_manager_id") or ""))
    if not p:
        return "The account manager"
    return "<@{0}>".format(p["slack_user_id"]) if p.get("slack_user_id") else esc(p.get("full_name"))


def run(db: Any, slack: Any, config: Any, seen: Optional[MutableMapping[str, Any]], today: date,
        cfg: Optional[Dict[str, Any]] = None, force: bool = False, write: bool = True,
        week_start: Optional[date] = None) -> Dict[str, Any]:
    cfg = cfg or load_config()
    day = str(cfg.get("weekday") or "Monday").strip().lower()
    if day not in DAYS:
        raise ValueError("config.json 'weekday' must be a day name, like Monday. It says: {0}".format(cfg.get("weekday")))
    if not force and today.weekday() != DAYS.index(day):
        return {"ok": True, "skipped": "today is not the report day ({0})".format(cfg["weekday"])}

    ctx = skillkit.Context(db, slack, config, seen)
    settings = ctx.settings()
    week = week_start or report_week(today)
    prev = week - timedelta(days=7)
    clients = db.select_all("clients", {"status": "eq.Active", "archived_at": "is.null"}, order="client_name") or []
    metrics: Dict[str, List[Dict[str, Any]]] = {}
    for r in db.select_all("daily_metrics", {"metric_date": "gte." + prev.isoformat()}, order="metric_date") or []:
        metrics.setdefault(str(r.get("client_id")), []).append(r)
    prev_weekly = {str(r.get("client_id")): r for r in
                   _read(db, "weekly_metrics", {"week_start": "eq." + prev.isoformat()}) or []}
    creatives = _read(db, "creatives", {"archived_at": "is.null"})
    campaigns = _read(db, "ad_campaigns", {"archived_at": "is.null"})
    team = _people(db)

    out: Dict[str, Any] = {"ok": True, "week_start": week.isoformat(), "written": 0, "posted": 0,
                           "no_numbers": [], "nothing_to_say": []}
    if campaigns is None:
        out["campaigns"] = "could not check: the ad_campaigns table could not be read"
    for client in clients:
        cid = str(client.get("id"))
        link = skillkit.os_link(settings, "clients/" + cid)
        try:
            now = sum_week(metrics.get(cid, []), week)
            before = sum_week(metrics.get(cid, []), prev) or prev_weekly.get(cid)
            if now is None:
                out["no_numbers"].append(client.get("client_name"))
            elif write:
                db.upsert("weekly_metrics", {"client_id": cid, "week_start": week.isoformat(), "spend": now["spend"],
                                             "leads": now["leads"], "calls_booked": now["calls_booked"]},
                          on_conflict="client_id,week_start")
                out["written"] += 1
            boards = boards_for(cid, week, creatives, campaigns)
            if now is None and cfg.get("skip_when_nothing_to_say") and not any(
                    v for k, v in boards.items() if k != "campaign_names"):
                out["nothing_to_say"].append(client.get("client_name"))
                continue
            draft = report_text(client, week, now, before, boards, cfg)
            key = "{0}:{1}:{2}".format(SKILL, cid, week.isoformat())
            if not skillkit.first_time(seen, key, hours=24 * 6):
                continue
            text = ("*Weekly report draft: {0}* (week of {1})\n"
                    "This was NOT sent to the client. {2} checks it, changes what is needed, and sends it.\n"
                    "```{3}```").format(esc(client.get("client_name")), short_date(week), _who(client, team),
                                        esc(draft)[:2600])
            if skillkit.post(ctx, cfg["channel"], BOT, text, link=link, button="Open the client"):
                out["posted"] += 1
        except Exception as e:  # noqa: BLE001 - one client must not stop the others
            out["ok"] = False
            skillkit.report_failure(ctx, SKILL, "report for {0}".format(client.get("client_name")), e, link)
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
    ap = argparse.ArgumentParser(description="Sum last week and draft each client's weekly report.")
    ap.add_argument("--now", action="store_true", help="write the week and post the drafts now, on any day")
    ap.add_argument("--dry-run", action="store_true", help="print what it would write and post (the default)")
    ap.add_argument("--week-start", help="the Monday of the week to report (YYYY-MM-DD); default last week")
    a = ap.parse_args(argv)
    week = date.fromisoformat(a.week_start) if a.week_start else None
    if week and week.weekday() != 0:
        print("--week-start must be a Monday. {0} is a {1}.".format(week, week.strftime("%A")))
        return 2
    live = a.now and not a.dry_run
    ctx = skillkit.context(needs=["SLACK_BOT_TOKEN"] if live else [])
    if live:
        out = run(ctx.db, ctx.slack, ctx.config, {}, date.today(), force=True, week_start=week)
    else:
        print("Dry run: nothing is written or posted. Add --now to do it.\n")
        fake = DryRun()
        out = run(ctx.db, fake, fake, {}, date.today(), force=True, write=False, week_start=week)
    print(skillkit.dump(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    skillkit.main_guard(main)
