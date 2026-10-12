"""Time: where the day went — sleep, exercise, calendar and screens, minute by minute — and what changed.

One rule for the whole page: every activity is measured from its own record (watch sleep, workouts,
calendar blocks, screen sessions counted once across devices). A minute can belong to two activities,
for example a lecture with the laptop open, so the activities can add up to more than the day.
Waking minutes that no record covers are "not recorded", never guessed. A day whose record for an
activity is missing (see context.TimeDay.known) shows nothing for that activity and is left out of
its average and of its normal, so a late Screen Time import or a night with the watch off never reads
as a drop.

The page does not name the biggest activity (screens would win almost every day, which says nothing).
It names what changed: each candidate is compared with your own normal, and a change counts only when
it lies clearly outside it, at least one width of the normal band past its edge (the width counts as at
least 30 minutes for a single day and 15 minutes a day for the 7-day average, or a tenth of the usual
value when that is larger). Measuring in band widths keeps the usual ups and downs quiet: an activity that swings by an hour
from day to day needs a bigger change than one that hardly moves. Of the clear changes, the biggest in
minutes is named, so the sentence and the minutes printed under it always agree.

A single day is compared with the middle half of the 28 days before it (stats.typical). The 7 days
shown are compared by their daily average with your usual 7-day averages (typical_week): an average of
7 days moves much less than one day does, so a band of single days would let a week with no exercise or
no classes at all read as normal.
"""
import math
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import ACTIVITIES, SCREEN_PARTS, Context, TimeDay, iso

SPAN = 7
HISTORY = 30
TOP_APPS = 12
KEYS = ACTIVITIES + SCREEN_PARTS + ("not_recorded",)
HOUR_KEYS = ("sleep", "exercise", "calendar") + SCREEN_PARTS
STALE = ("sleep", "exercise", "screen")  # records that arrive by import and can fall behind
SAME_WORKOUT_GAP_MIN = 60  # stretches of one workout split by a pause are listed as one

# What "what changed" may name, in the order that breaks ties. The screen total is not one of them:
# it is the biggest every day, and its parts (fun, focus, communication) say what actually moved.
CANDIDATES = ("fun", "focus", "communication", "exercise", "calendar", "sleep")
NORMAL_KEYS = CANDIDATES + ("screen", "not_recorded")  # the tiles also show these two against their normal
BETTER = {"fun": "lower", "focus": "higher", "communication": "none", "exercise": "higher", "calendar": "none",
          "sleep": "higher", "screen": "none", "not_recorded": "none"}
STANDOUT_MIN = 1.0      # a change counts when it lies at least one band width outside normal
DAY_MIN_WIDTH = 30      # minutes: a single day's band counts as at least this wide when measuring,
SPAN_MIN_WIDTH = 15     # minutes a day: and a 7-day average's band as at least this wide,
MIN_WIDTH_SHARE = 0.10  # or a tenth of the usual value if larger, so a few minutes off a steady habit are no change
WEEK_MIN_DAYS = 4       # a 7-day average in the normal needs at least this many days with the record


def _owner(key: str) -> str:
    """The activity whose record a total belongs to."""
    if key in SCREEN_PARTS:
        return "screen"
    return key


def _average(days: List[date], ctx: Context) -> Dict[str, Any]:
    time = ctx.time_days()
    have = [time[d] for d in days if d in time]
    totals = [td.totals() for td in have]
    counts = {k: sum(1 for t in totals if t[k] is not None) for k in KEYS}
    avg = {k: (sum(t[k] for t in totals if t[k] is not None) / counts[k] if counts[k] else None) for k in KEYS}
    hours = []
    for h in range(24):
        slot = {}
        for k in HOUR_KEYS:
            known = [td for td in have if td.known[_owner(k)]]
            slot[k] = sum(td.by_hour[h].get(k, 0.0) for td in known) / len(known) if known else None
        hours.append(slot)
    screen = ctx.screen_days()
    sd_have = [screen[d] for d in days if d in screen]
    n_screen = len(sd_have)
    apps: Dict[tuple, float] = {}
    for sd in sd_have:
        for key, minutes in sd.by_app.items():
            apps[key] = apps.get(key, 0.0) + minutes / n_screen
    devices: Dict[str, float] = {}
    for (_, device, _), minutes in apps.items():
        devices[device] = devices.get(device, 0.0) + minutes
    longest = sum(sd.longest_focus for sd in sd_have) / n_screen if sd_have else None
    exercise = [t["exercise"] for t in totals if t["exercise"] is not None]
    return {"from": iso(days[0]), "to": iso(days[-1]), "n": len(have), "avg": avg, "known": counts, "by_hour": hours,
            "apps": [{"app": a, "device": dv, "category": c, "minutes": m}
                     for (a, dv, c), m in sorted(apps.items(), key=lambda kv: -kv[1])[:TOP_APPS]],
            "devices": devices, "longest_focus": longest,
            "exercise_days": sum(1 for v in exercise if v > 0), "exercise_known": len(exercise),
            "untimed_exercise": any(td.untimed_exercise for td in have)}


# ---- what changed, compared with your normal ----------------------------------------------------
def normal_series(ctx: Context) -> Dict[str, stats.Series]:
    """Daily minutes per key, only on whole days whose record for it exists: a day without Screen
    Time is not a zero-screen day, so it never pulls the normal down."""
    time = ctx.time_days()
    out: Dict[str, stats.Series] = {k: {} for k in NORMAL_KEYS}
    for d in data_days(ctx):
        totals = time[d].totals()
        for k in NORMAL_KEYS:
            if totals[k] is not None:
                out[k][d] = totals[k]
    return out


def typical_week(values: stats.Series, first: date) -> Optional[Dict[str, float]]:
    """Your normal for a 7-day average: the middle half of the 7-day averages ending on each of the 28
    days before ``first``. Each average is over the days in it that have the record (at least
    WEEK_MIN_DAYS of the 7), and it needs at least stats.MIN_BASELINE of them. ``days`` is how many
    averages it rests on."""
    means = []
    for k in range(1, stats.BASELINE_DAYS + 1):
        end = first - timedelta(days=k)
        week = [values[end - timedelta(days=j)] for j in range(SPAN) if end - timedelta(days=j) in values]
        if len(week) >= WEEK_MIN_DAYS:
            means.append(sum(week) / len(week))
    if len(means) < stats.MIN_BASELINE:
        return None
    q1, median, q3 = statistics.quantiles(means, n=4, method="inclusive")
    return {"median": median, "q1": q1, "q3": q3, "days": len(means)}


def _whole(minutes: Optional[float]) -> Optional[float]:
    """Whole minutes, rounded the way the page prints them (half up), so a chip never says "above
    normal" about a value that reads the same as the top of its normal."""
    return None if minutes is None else float(math.floor(minutes + 0.5))


def score(value: Optional[float], band: Optional[Dict[str, float]], min_width: float) -> float:
    """How far ``value`` lies outside the normal band, in band widths (the width counts as at least
    ``min_width`` minutes or a tenth of the median); 0 inside it or when unknown."""
    if value is None or band is None:
        return 0.0
    if value > band["q3"]:
        outside = value - band["q3"]
    elif value < band["q1"]:
        outside = band["q1"] - value
    else:
        return 0.0
    return outside / max(band["q3"] - band["q1"], min_width, MIN_WIDTH_SHARE * band["median"])


def compare(key: str, value: Optional[float], band: Optional[Dict[str, float]], min_width: float) -> Dict[str, Any]:
    """``value`` against ``band`` in whole minutes. ``clear`` = far enough outside to count as a change."""
    v = _whole(value)
    b = {k: _whole(band[k]) for k in ("q1", "median", "q3")} if band is not None else None
    state = stats.classify(v, b)
    s = score(v, b, min_width)
    return {"key": key, "value": value, "band": band, "state": state,
            "delta": value - band["median"] if state is not None else None,
            "score": s, "clear": s >= STANDOUT_MIN, "tone": stats.tone(state, BETTER[key])}


def ranked(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The clear changes first, biggest in minutes first; then the rest, furthest outside first.
    Ties keep the order of CANDIDATES."""
    order = {k: i for i, k in enumerate(CANDIDATES)}
    return sorted(changes, key=lambda c: (not c["clear"], -abs(c["delta"]) if c["clear"] else -c["score"],
                                          order.get(c["key"], len(order))))


def standout(changes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The biggest clear change among the candidates, or None when nothing is clearly outside normal."""
    best = next(iter(ranked([c for c in changes if c["key"] in CANDIDATES])), None)
    return best if best is not None and best["clear"] else None


def _day(td: TimeDay, series: Dict[str, stats.Series]) -> Dict[str, Any]:
    totals = td.totals()
    changes = [compare(k, totals[k], stats.typical(series[k], td.day), DAY_MIN_WIDTH) for k in CANDIDATES]
    best = standout(changes)
    return {"date": iso(td.day), "totals": totals, "minutes_in_day": td.length,
            "standout": {k: best[k] for k in ("key", "value", "band", "state", "delta", "score", "tone")} if best else None,
            "compared": sum(1 for c in changes if c["state"] is not None)}


def _span_changes(span: Dict[str, Any], first: date, series: Dict[str, stats.Series]) -> Dict[str, Any]:
    """The span's daily average against your usual 7-day averages before its first day. An average
    that rests on fewer than half of the shown days is shown but not compared."""
    metrics = {}
    for k in NORMAL_KEYS:
        enough = span["known"][k] * 2 >= span["n"]
        m = compare(k, span["avg"][k], typical_week(series[k], first) if enough else None, SPAN_MIN_WIDTH)
        m.update(known=span["known"][k], few=not enough)
        metrics[k] = m
    changes = ranked([metrics[k] for k in CANDIDATES])
    return {"metrics": metrics, "changes": changes, "standout": standout(changes),
            "compared": sum(1 for c in changes if c["state"] is not None)}


def _workouts(ctx: Context, first: date, last: date) -> List[Dict[str, Any]]:
    """Workouts that start in [first, last]. Stretches of one workout that a pause split into rows
    (same type and source, close together) are listed as one, with the minutes actually moving."""
    rows = sorted((w for w in ctx.store.rows("workouts") if w["end"] > w["start"] and first <= w["start"].date() <= last),
                  key=lambda w: w["start"])
    out: List[Dict[str, Any]] = []
    for w in rows:
        minutes = (w["end"] - w["start"]).total_seconds() / 60
        prev = out[-1] if out else None
        if (prev and prev["type"] == w["type"] and prev["source"] == w.get("source")
                and timedelta(0) <= w["start"] - prev["_end"] <= timedelta(minutes=SAME_WORKOUT_GAP_MIN)):
            prev["minutes"] += minutes
            prev["_end"] = max(prev["_end"], w["end"])
            prev["end"] = iso(prev["_end"])
            if w.get("kcal") is not None:
                prev["kcal"] = (prev["kcal"] or 0.0) + w["kcal"]
            continue
        out.append({"start": iso(w["start"]), "end": iso(w["end"]), "_end": w["end"], "type": w["type"],
                    "source": w.get("source"), "minutes": minutes, "kcal": w.get("kcal")})
    for w in out:
        del w["_end"]
    return out


def _stale(ctx: Context, time: Dict[date, TimeDay], span_to: date) -> List[Dict[str, Any]]:
    """Records that stop before the last shown day, with the last whole day that has one. For screens
    that is the day before the last imported one, which the import probably cut off (context.time_days)."""
    out = []
    for activity in STALE:
        last = max((d for d, td in time.items() if d < ctx.today and td.known[activity]), default=None)
        if last is None or last < span_to:
            out.append({"activity": activity, "last": iso(last)})
    return out


def data_days(ctx: Context) -> List[date]:
    """Every whole day (today is not over) that has a record of its own, oldest first."""
    return sorted(d for d, td in ctx.time_days().items() if d < ctx.today and td.admitted)


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    time = ctx.time_days()
    end = date.fromisoformat(day) if day else ctx.today - timedelta(days=1)
    every = data_days(ctx)
    whole = [d for d in every if d <= end]
    recent, before = whole[-SPAN:], whole[-2 * SPAN:-SPAN]  # "before" only feeds the "Earlier" link
    newest = every[-1] if every else None
    base = {"page": "time", "today": iso(ctx.today), "now": iso(ctx.now), "newest": iso(newest)}
    if not recent:
        return {**base, "day": iso(end), "empty": True,
                "next": iso(every[min(SPAN, len(every)) - 1]) if every else None}
    last = recent[-1]
    history = []
    for k in range(HISTORY - 1, -1, -1):
        d = last - timedelta(days=k)
        td = time.get(d)
        history.append({"date": iso(d), "totals": td.totals() if td else None, "in_span": d in recent,
                        "minutes_in_day": td.length if td else ctx.day_length(d)})
    plan = ctx.cfg.screen
    series = normal_series(ctx)
    span = _average(recent, ctx)
    span.update(_span_changes(span, recent[0], series))
    span["days"] = [_day(time[d], series) for d in recent]
    span["workouts"] = _workouts(ctx, recent[0], last)
    span["stale"] = _stale(ctx, time, last)
    # step by days with records, like "Earlier": the next page ends 7 such days later (or on the newest)
    later = [d for d in every if d > last]
    return {**base, "day": iso(last), "empty": False, "span": span,
            "baseline_days": stats.BASELINE_DAYS, "baseline_min": stats.MIN_BASELINE,
            "history": history, "devices_order": ctx.cfg.devices,
            "limits": {"fun_max_min": plan.entertainment_max_hours * 60 if plan.entertainment_max_hours else None,
                       "focus_min_min": plan.work_min_hours * 60 if plan.work_min_hours else None},
            "prev": iso(before[-1]) if before else None,
            "next": iso(later[min(SPAN, len(later)) - 1]) if later else None}


def static_params(ctx: Context, steps: int = 3) -> List[Optional[str]]:
    """The pages a static site needs so that every "Earlier" and "Later" link it shows exists:
    the latest page, the newest day (what "Later" from the page before it points at, the same
    numbers as the latest page), and ``steps`` pages back along the "Earlier" chain."""
    params: List[Optional[str]] = [None]
    page = build(ctx)
    if page.get("newest"):
        params.append(page["newest"])
    for _ in range(steps):
        if page.get("empty") or not page.get("prev"):
            break
        params.append(page["prev"])
        page = build(ctx, page["prev"])
    return params
