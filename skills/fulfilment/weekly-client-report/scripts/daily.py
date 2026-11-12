"""The daily job calls run() once a day. The rules are in weekly_client_report.py."""

from __future__ import annotations

import sys
from pathlib import Path

for _up in Path(__file__).resolve().parents:
    _kit = [k for k in (_up / "skills/_kit", _up / "core/skills/_kit") if (k / "skillkit.py").exists()]
    if _kit:
        sys.path.insert(0, str(_kit[0]))
        break
import skillkit  # noqa: E402,F401

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weekly_client_report  # noqa: E402


def run(db, slack, config, seen, today):
    return weekly_client_report.run(db, slack, config, seen, today)
