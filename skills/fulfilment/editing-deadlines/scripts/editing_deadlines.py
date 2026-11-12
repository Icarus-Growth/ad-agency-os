"""Editing deadlines: one post a day with the Editing pipeline cards that are late, due today
or due soon, grouped by the person who must act.

A card counts when it has a due date, it is not finished (only a '100 - ...' stage is
finished) and it is not archived. The main post gives the counts and the board link. The
thread under it has one reply per person, with a link to each card.

The daily job runs it once a day (scripts/daily.py). On demand:

    python3 skills/fulfilment/editing-deadlines/scripts/editing_deadlines.py          (dry run)
    python3 skills/fulfilment/editing-deadlines/scripts/editing_deadlines.py --now    (posts)

It only reads. It writes nothing to the database.
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
import re  # noqa: E402
from datetime import date, timedelta  # noqa: E402
from typing import Any, Dict, List, MutableMapping, Optional  # noqa: E402

SKILL = "editing-deadlines"
BOT = "⏰ Editing Deadlines"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "config.json"
DEFAULTS: Dict[str, Any] = {"due_soon_days": 2, "channel": "task-updates", "board": "creatives",
                            "board_label": "Editing pipeline", "name_column": "creative_name",
                            "max_lines_per_person": 30}
NOBODY = "Nobody is set to do these"


def load_config(path: Path = CONFIG_FILE) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update({k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")})
    try:
        cfg["due_soon_days"] = int(cfg["due_soon_days"])
    except (TypeError, ValueError):
        raise ValueError("config.json 'due_soon_days' must be a whole number of days, like 2. It says: {0}".format(
            cfg.get("due_soon_days")))
    return cfg


def esc(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def finished(stage: Any) -> bool:
    m = re.match(r"^\s*(\d+)", str(stage or ""))
    return bool(m) and int(m.group(1)) >= 100


def short_date(d: date) -> str:
    return "{0} {1} {2}".format(d.strftime("%a"), d.day, d.strftime("%b"))


def bucket(due: date, today: date) -> str:
    if due < today:
        return "Overdue"
    if due == today:
        return "Due today"
    return "Due soon"


def when(due: date, today: date) -> str:
    late = (today - due).days
    if late > 0:
        return "{0} day{1} late".format(late, "" if late == 1 else "s")
    if late == 0:
        return "due today"
    return "due {0}".format(short_date(due))


def collect(cards: List[Dict[str, Any]], today: date, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The cards that count, each with its due date as a date. Pure."""
    last = today + timedelta(days=cfg["due_soon_days"])
    out = []
    for c in cards:
        if finished(c.get("stage")) or c.get("archived_at") or not c.get("due_date"):
            continue
        due = date.fromisoformat(str(c["due_date"])[:10])
        if due <= last:
            out.append(dict(c, _due=due))
    return sorted(out, key=lambda c: (c["_due"], str(c.get(cfg["name_column"]) or "")))


def person_reply(person: str, cards: List[Dict[str, Any]], clients: Dict[str, str], settings: Dict[str, Any],
                 today: date, cfg: Dict[str, Any]) -> str:
    lines = ["*{0}*".format(person)]
    shown = 0
    for title in ("Overdue", "Due today", "Due soon"):
        group = [c for c in cards if bucket(c["_due"], today) == title]
        if not group:
            continue
        lines.append("_{0}_".format(title))
        for c in group:
            if shown >= int(cfg["max_lines_per_person"]):
                break
            name = esc(c.get(cfg["name_column"]) or "Untitled card")
            link = skillkit.card_link(settings, cfg["board"], str(c.get("id")))
            label = "<{0}|{1}>".format(link, name) if link else name
            lines.append("• {0} ({1}), {2}, {3}".format(label, esc(clients.get(str(c.get("client_id")), "no client")),
                                                      esc(c.get("stage")), when(c["_due"], today)))
            shown += 1
    if len(cards) > shown:
        lines.append("…and {0} more on the board.".format(len(cards) - shown))
    return "\n".join(lines)


def run(db: Any, slack: Any, config: Any, seen: Optional[MutableMapping[str, Any]], today: date,
        cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or load_config()
    ctx = skillkit.Context(db, slack, config, seen)
    settings = ctx.settings()
    board_link = skillkit.os_link(settings, "tasks/" + cfg["board"])
    last = today + timedelta(days=cfg["due_soon_days"])
    try:
        rows = db.select_all(cfg["board"], {"due_date": "lte." + last.isoformat(), "archived_at": "is.null"},
                             order="due_date")
        cards = collect(rows or [], today, cfg)
    except Exception as e:  # noqa: BLE001
        skillkit.report_failure(ctx, SKILL, "read the {0} board".format(cfg["board_label"]), e, board_link)
        return {"ok": False, "error": str(e)[:200]}

    out: Dict[str, Any] = {"ok": True, "cards": len(cards), "people": 0, "posted": False}
    for title in ("Overdue", "Due today", "Due soon"):
        out[title] = sum(1 for c in cards if bucket(c["_due"], today) == title)
    if not cards:
        return out
    key = "{0}:{1}".format(SKILL, today.isoformat())
    if not skillkit.first_time(seen, key, hours=20):
        out["skipped"] = "already posted today"
        return out

    ids = sorted({str(c.get("client_id")) for c in cards if c.get("client_id")})
    clients = {str(r["id"]): r.get("client_name") or "" for r in
               (db.select_all("clients", {"id": "in.({0})".format(",".join(ids))}) if ids else [])}
    team = {str(t["id"]): t for t in db.select_all("team", {}) or []}
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for c in cards:
        groups.setdefault(str(c.get("assignee_id") or ""), []).append(c)

    def label(person_id: str) -> str:
        p = team.get(person_id)
        if not p:
            return NOBODY
        name = esc(p.get("full_name") or "Someone")
        return "{0} (<@{1}>)".format(name, p["slack_user_id"]) if p.get("slack_user_id") else name

    order = sorted(groups, key=lambda pid: (pid == "", label(pid)))
    out["people"] = len([p for p in order if p])
    head = ("*{0} deadlines, {1}*\n{2} overdue, {3} due today, {4} due in the next {5} days.\n"
            "Each person's cards are in the thread. Move a card on when it is done, or change its due date.").format(
        cfg["board_label"], short_date(today), out["Overdue"], out["Due today"], out["Due soon"], cfg["due_soon_days"])
    ts = skillkit.post(ctx, cfg["channel"], BOT, head, link=board_link, button="Open the board")
    if not ts:
        return out
    channel = ctx.config.channel_id(cfg["channel"])
    for pid in order:
        ctx.slack.post(channel, BOT, person_reply(label(pid), groups[pid], clients, settings, today, cfg),
                       thread_ts=ts)
    out["posted"] = True
    return out


class DryRun:
    """Stands in for Slack and the channels: prints each post instead of sending it."""

    def channel_id(self, key: str) -> str:
        return "#" + key

    def post(self, channel: str, bot_name: str, text: str, blocks: Optional[list] = None,
             thread_ts: Optional[str] = None) -> str:
        where = "the thread" if thread_ts else channel
        print("--- would post in {0} as {1}:\n{2}\n".format(where, bot_name, text))
        return "dry-run"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Post the Editing pipeline cards that are late or due soon.")
    ap.add_argument("--now", action="store_true", help="post now")
    ap.add_argument("--dry-run", action="store_true", help="print what it would post (the default)")
    ap.add_argument("--today", help="as if today were this date (YYYY-MM-DD)")
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
