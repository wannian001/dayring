"""Data: what arrived, from which device, what is missing, and which rows could not be read. The page to check when a
number looks wrong.

Each stream is listed under the device it comes from, the way a person thinks of their data: the watch (sleep, HRV,
resting heart rate, activity minutes), the phone (steps, weight from a scale or typed into Health, the meals a
food app writes into Health), the Mac (Screen Time, with the iPhone and iPad when they share it), and files brought
in by hand (soreness check-ins from the Recovery page, self-report). The first three reach this computer through the iPhone app and the Mac app; the page says
when each last did, outside the demo."""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import capture, state
from ..context import Context, iso
from ..schema import TABLES
from .food import food_days

DAYS = 90
DEVICES = ("watch", "phone", "mac", "manual")
STREAMS = [  # key, table, column (None = any row that day), stale after N days, the device it comes from
    ("sleep", "body_daily", "sleep_min", 2, "watch"),
    ("hrv", "body_daily", "hrv_ms", 2, "watch"),
    ("resting_hr", "body_daily", "resting_hr", 2, "watch"),
    ("exercise", "body_daily", "exercise_min", 2, "watch"),
    ("steps", "body_daily", "steps", 2, "phone"),
    ("weight", "body_daily", "weight_kg", 7, "phone"),
    ("food", "meals", None, 3, "phone"),  # a full day = at least two main meals logged; one meal = partial
    ("screen", "screen_sessions", None, 2, "mac"),
    ("sore", "soreness", None, 7, "manual"),
    ("self", "self_report", None, 7, "manual"),
]


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    today = ctx.today
    first = today - timedelta(days=DAYS - 1)
    body = ctx.store.by_date("body_daily")
    screen = ctx.screen_days()
    selfr = ctx.store.by_date("self_report")
    sore = {r["date"] for r in ctx.store.rows("soreness")}
    meals = food_days(ctx, today) if ctx.store.load("meals").present else {}
    streams = []
    for key, table, column, stale_after, device in STREAMS:
        if table in ("meals", "self_report", "soreness") and not ctx.store.load(table).present:
            continue  # optional: someone who does not log food, soreness or how the day felt gets no "never arrived" row
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
            elif table == "meals":
                x = meals.get(d)
                mark = "0" if x is None else ("1" if x["main"] >= 2 else "p")
            elif table == "soreness":
                mark = "1" if d in sore else "0"
            else:
                mark = "1" if d in selfr else "0"
            marks.append(mark)
        if table == "body_daily":
            have = [d for d, r in body.items() if r.get(column) is not None]
        elif table == "screen_sessions":
            have = list(screen)
        elif table == "meals":
            have = list(meals)
        elif table == "soreness":
            have = list(sore)
        else:
            have = list(selfr)
        last = max(have) if have else None
        behind = (today - last).days if last else None
        streams.append({"key": key, "table": table, "device": device, "marks": "".join(marks), "last": iso(last), "days_behind": behind,
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
    # how the data reached this computer: the iPhone app's last package and the Mac app's last collection
    receipt = None if ctx.cfg.demo else capture.last_receipt(ctx.cfg)
    collected = None if ctx.cfg.demo else state.read_json(state.folder(ctx.cfg) / "collect.json")
    return {"page": "data", "today": iso(today), "now": iso(ctx.now), "first": iso(first), "days": DAYS,
            "devices": [d for d in DEVICES if any(s["device"] == d for s in streams)],
            "carriers": {"phone": receipt.get("landed_at") if receipt else None,
                         "mac": collected.get("at") if collected else None},
            "streams": streams, "tables": tables, "demo": ctx.cfg.demo,
            "ok": all(s["status"] == "ok" for s in streams if s["key"] in ("sleep", "hrv", "screen"))}
