"""Data: what arrived, what is missing, and which rows could not be read. The page to check when a number looks wrong."""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ..context import Context, iso
from ..schema import TABLES

DAYS = 90
STREAMS = [  # key, table, column (None = any row that day), stale after N days
    ("sleep", "body_daily", "sleep_min", 2),
    ("hrv", "body_daily", "hrv_ms", 2),
    ("steps", "body_daily", "steps", 2),
    ("weight", "body_daily", "weight_kg", 7),
    ("screen", "screen_sessions", None, 2),
    ("self", "self_report", None, 7),
    ("ai", "ai_work", None, 7),  # AI agents: a day without use is a real zero, so only arrivals are marked
]


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    today = ctx.today
    first = today - timedelta(days=DAYS - 1)
    body = ctx.store.by_date("body_daily")
    screen = ctx.screen_days()
    selfr = ctx.store.by_date("self_report")
    ai = ctx.ai_days()
    streams = []
    for key, table, column, stale_after in STREAMS:
        if table == "ai_work" and not ctx.store.load("ai_work").present:
            continue  # optional: someone who does not use AI agents gets no "never arrived" row
        marks: List[str] = []
        last: Optional[date] = None
        for k in range(DAYS):
            d = first + timedelta(days=k)
            if table == "body_daily":
                row = body.get(d)
                v = row.get(column) if row else None
                mark = "0" if v is None else ("p" if row.get("complete") is False and column == "steps" else "1")
            elif table == "screen_sessions":
                sd = screen.get(d)
                mark = "1" if sd and sd.total >= 60 else ("p" if sd else "0")
            elif table == "ai_work":
                ad = ai.get(d)
                mark = "1" if ad and (ad.you or ad.other or ad.prompts) else "0"
            else:
                mark = "1" if d in selfr else "0"
            marks.append(mark)
        if table == "body_daily":
            have = [d for d, r in body.items() if r.get(column) is not None]
        elif table == "screen_sessions":
            have = list(screen)
        elif table == "ai_work":
            have = [d for d, ad in ai.items() if ad.you or ad.other or ad.prompts]
        else:
            have = list(selfr)
        last = max(have) if have else None
        behind = (today - last).days if last else None
        streams.append({"key": key, "table": table, "marks": "".join(marks), "last": iso(last), "days_behind": behind,
                        "stale_after": stale_after,
                        "status": "missing" if last is None else ("stale" if behind > stale_after else "ok"),
                        "days_with_data": marks.count("1")})
    tables = []
    for name, table in TABLES.items():
        loaded = ctx.store.load(name)
        tables.append({"name": name, "file": table.filename, "present": loaded.present, "rows": len(loaded.rows),
                       "modified": iso(loaded.modified) if loaded.modified else None,
                       "problems": [p.as_dict() for p in loaded.problems[:12]], "problem_count": len(loaded.problems),
                       "doc": table.doc})
    return {"page": "data", "today": iso(today), "now": iso(ctx.now), "first": iso(first), "days": DAYS,
            "streams": streams, "tables": tables, "demo": ctx.cfg.demo,
            "ok": all(s["status"] == "ok" for s in streams if s["key"] in ("sleep", "hrv", "screen"))}
