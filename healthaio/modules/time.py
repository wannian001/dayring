"""Stimulation (#time): how stimulating your days are, how that is spread, and how your body answers.

The page used to be "Where time went" and keeps the key ``time``, so old links still open it. Where the hours of a
day went is on the Today page's day ring; this page asks a different question: how much dense, high-reward input did
your days hold, and what did your body do afterwards?

Hormones and transmitters (dopamine, cortisol, melatonin) cannot be measured by a phone or a watch, so the page never
shows a number for them. It measures what can be measured around them:

- What goes in: five signals from Screen Time, each the daily average of the shown 7 days against your normal (the
  middle half of your 7-day averages ending on each of the 28 days before the first shown day, at least
  stats.MIN_BASELINE of them, each from at least WEEK_MIN_DAYS days with the record):
  - fun: minutes in entertainment and social apps, screens counted once across devices. The level the page leads
    with.
  - before_sleep: entertainment & social minutes in the hour before falling asleep that night. A night whose hour
    sits partly on a day without a whole screen record is unknown, never 0.
  - switches: app switches per screen hour (the Drain page's measure): how fragmented the input is.
  - ratio: screens at once, device time over clock time, kept in hundredths (142 = 1.42x).
  - longest_focus: the longest stretch on work or learning apps; the other side of the same coin, longer is better.
  A value is above or below normal only when it lies at least one band width outside the band (the width counts as
  at least MIN_WIDTH of its unit, or a tenth of the usual value when that is larger; the ratio has no tenth rule).
  An average that rests on fewer than half of the shown days is shown but not compared.
- How the body answers (response): over the last RESPONSE_DAYS days, the night and the next morning after days with
  entertainment & social above your own median of those days, against the other days; and after evenings with more
  than CALM_MIN minutes of it in the last hour, against calm ones. Outcomes: when you fell asleep, how long you slept,
  the next morning's HRV (percent against your normal) and resting heart rate (beats against your normal).
  Difference of means with a 95% interval, at least stats.MIN_GROUP_DAYS days in each group, Benjamini-Hochberg
  across all of them; only what survives is called a difference. Associations, never causes.
- The long view (trend): 90 days of entertainment & social minutes and of the longest focus stretch.
"""
import math
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import FUN, SCREEN_PARTS, Context, TimeDay, iso
from . import drain as drain_page

SPAN = 7
TOP_APPS = 8
STALE = ("screen",)  # the record this page rests on, which arrives by import and can fall behind
STIM_KEYS = ("fun", "before_sleep", "switches", "ratio", "longest_focus")
UNITS = {"fun": "min", "before_sleep": "min", "switches": "per_hour", "ratio": "ratio", "longest_focus": "min"}
BETTER = {"fun": "lower", "before_sleep": "lower", "switches": "lower", "ratio": "lower", "longest_focus": "higher"}
MIN_WIDTH = {"fun": 15, "before_sleep": 5, "switches": 2, "ratio": 5, "longest_focus": 5}  # least band widths
MIN_WIDTH_SHARE = 0.10  # or a tenth of the usual value if larger, so a few minutes off a steady habit are no change
STANDOUT_MIN = 1.0      # a change counts when it lies at least one band width outside normal
WEEK_MIN_DAYS = 4       # a 7-day average in the normal needs at least this many days with the record
BEFORE_SLEEP = 60       # minutes before falling asleep
CALM_MIN = 15           # entertainment & social minutes in that hour that still count as a calm evening
RESPONSE_DAYS = 90
EXPOSURES = ("fun_high", "late_fun")
OUTCOMES = ("asleep", "sleep_min", "hrv", "resting_hr")
OUTCOME_BETTER = {"asleep": "lower", "sleep_min": "higher", "hrv": "higher", "resting_hr": "lower"}
OUTCOME_UNITS = {"asleep": "min", "sleep_min": "min", "hrv": "%", "resting_hr": "bpm"}


def data_days(ctx: Context) -> List[date]:
    """Every whole day (today is not over) that has a record of its own, oldest first."""
    return sorted(d for d, td in ctx.time_days().items() if d < ctx.today and td.admitted)


# ---- what goes in ------------------------------------------------------------------------------
def stim_series(ctx: Context) -> Dict[str, stats.Series]:
    """Each signal per day, only on days whose screen record is whole (a day without Screen Time is not a calm day),
    plus the clock and device minutes the ratio of several days is worked out from."""
    time, screen = ctx.time_days(), ctx.screen_days()
    whole = [d for d in data_days(ctx) if time[d].known["screen"] and d in screen]
    known = set(whole)
    switches = drain_page.daily_series(ctx, ctx.today)["switches"]
    body = ctx.store.by_date("body_daily")
    out: Dict[str, stats.Series] = {k: {} for k in STIM_KEYS + ("screen", "stacked")}
    for d in whole:
        totals = time[d].totals()
        out["fun"][d] = totals["fun"]
        out["screen"][d] = totals["screen"]
        if totals["stacked"] is not None:
            out["stacked"][d] = totals["stacked"]
        if totals["ratio"] is not None:
            out["ratio"][d] = totals["ratio"]
        out["longest_focus"][d] = screen[d].longest_focus
        if d in switches:
            out["switches"][d] = switches[d]
        start = (body.get(d + timedelta(days=1)) or {}).get("sleep_start")
        if start and (start - timedelta(minutes=BEFORE_SLEEP)).date() in known and (start - timedelta(minutes=1)).date() in known:
            out["before_sleep"][d] = ctx.fun_before_sleep(d)
    return out


# ---- your normal --------------------------------------------------------------------------------
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


def typical_week_ratio(stacked: stats.Series, clock: stats.Series, first: date) -> Optional[Dict[str, float]]:
    """Your normal for the stacking ratio of 7 days: like typical_week, but each 7 days' ratio is their
    device time over their clock time (the way the shown days' ratio is worked out), in hundredths."""
    ratios = []
    for k in range(1, stats.BASELINE_DAYS + 1):
        end = first - timedelta(days=k)
        week = [end - timedelta(days=j) for j in range(SPAN)]
        both = [d for d in week if d in stacked and d in clock]
        screen = sum(clock[d] for d in both)
        if len(both) >= WEEK_MIN_DAYS and screen > 0:
            ratios.append(sum(stacked[d] for d in both) / screen * 100)
    if len(ratios) < stats.MIN_BASELINE:
        return None
    q1, median, q3 = statistics.quantiles(ratios, n=4, method="inclusive")
    return {"median": median, "q1": q1, "q3": q3, "days": len(ratios)}


def _whole(minutes: Optional[float]) -> Optional[float]:
    """Whole minutes, rounded the way the page prints them (half up), so a chip never says "above
    normal" about a value that reads the same as the top of its normal."""
    return None if minutes is None else float(math.floor(minutes + 0.5))


def score(value: Optional[float], band: Optional[Dict[str, float]], min_width: float,
          share: float = MIN_WIDTH_SHARE) -> float:
    """How far ``value`` lies outside the normal band, in band widths (the width counts as at least
    ``min_width`` minutes or ``share`` of the median); 0 inside it or when unknown."""
    if value is None or band is None:
        return 0.0
    if value > band["q3"]:
        outside = value - band["q3"]
    elif value < band["q1"]:
        outside = band["q1"] - value
    else:
        return 0.0
    return outside / max(band["q3"] - band["q1"], min_width, share * band["median"])


def _rounded(key: str, value: Optional[float]) -> Optional[float]:
    """As the page prints it: switches to a tenth, everything else whole (see _whole)."""
    if value is None:
        return None
    return round(value, 1) if key == "switches" else _whole(value)


def compare(key: str, value: Optional[float], band: Optional[Dict[str, float]]) -> Dict[str, Any]:
    """``value`` against ``band``, both as printed. ``clear`` = far enough outside to count as a change."""
    v = _rounded(key, value)
    b = {k: _rounded(key, band[k]) for k in ("q1", "median", "q3")} if band is not None else None
    state = stats.classify(v, b)
    s = score(v, b, MIN_WIDTH[key], 0.0 if key == "ratio" else MIN_WIDTH_SHARE)
    return {"key": key, "unit": UNITS[key], "value": value, "band": band, "state": state,
            "delta": value - band["median"] if state is not None else None,
            "score": s, "clear": s >= STANDOUT_MIN, "tone": stats.tone(state, BETTER[key])}


def metrics(recent: List[date], series: Dict[str, stats.Series]) -> Dict[str, Dict[str, Any]]:
    """The shown days' daily average of each signal against your usual 7-day averages before the first of them."""
    out = {}
    for key in STIM_KEYS:
        have = [d for d in recent if d in series[key]]
        enough = len(have) * 2 >= len(recent)
        if key == "ratio":  # device time over clock time of the days together, like its normal
            both = [d for d in have if d in series["stacked"] and d in series["screen"]]
            clock = sum(series["screen"][d] for d in both)
            value = sum(series["stacked"][d] for d in both) / clock * 100 if clock else None
            band = typical_week_ratio(series["stacked"], series["screen"], recent[0]) if enough else None
        else:
            value = sum(series[key][d] for d in have) / len(have) if have else None
            band = typical_week(series[key], recent[0]) if enough else None
        m = compare(key, value, band)
        m.update(known=len(have), few=not enough)
        out[key] = m
    return out


def level(m: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """The headline: entertainment & social clearly above / below your normal, within it, or None (no normal yet)."""
    fun = m["fun"]
    if fun["state"] is None:
        return None
    return fun["state"] if fun["state"] in ("high", "low") and fun["clear"] else "normal"


def fun_hours(ctx: Context, days: List[date]) -> Optional[List[float]]:
    """Entertainment & social minutes per hour of the day, averaged over ``days`` with a whole screen record."""
    time = ctx.time_days()
    have = [time[d] for d in days if d in time and time[d].known["screen"]]
    if not have:
        return None
    return [sum(td.by_hour[h].get("fun", 0.0) for td in have) / len(have) for h in range(24)]


def fun_apps(ctx: Context, days: List[date]) -> List[Dict[str, Any]]:
    """Where the entertainment & social minutes came from: apps and sites a day, on each device."""
    screen = ctx.screen_days()
    have = [screen[d] for d in days if d in screen]
    apps: Dict[tuple, float] = {}
    for sd in have:
        for (app, device, category), minutes in sd.by_app.items():
            if category in FUN:
                apps[(app, device, category)] = apps.get((app, device, category), 0.0) + minutes / len(have)
    return [{"app": a, "device": dv, "category": c, "minutes": m}
            for (a, dv, c), m in sorted(apps.items(), key=lambda kv: -kv[1])[:TOP_APPS]]


# ---- how the body answers ------------------------------------------------------------------------
def response(ctx: Context, last: date, series: Dict[str, stats.Series]) -> Dict[str, Any]:
    """The night and next morning after stimulating days against the others (see the module's docstring)."""
    first = last - timedelta(days=RESPONSE_DAYS - 1)
    fun = {d: v for d, v in series["fun"].items() if first <= d <= last}
    late = {d: v for d, v in series["before_sleep"].items() if first <= d <= last}
    rows_all = [r for r in ctx.store.rows("body_daily") if r.get("complete") is not False]
    body = {r["date"]: r for r in rows_all}
    hrv, rhr = stats.series(rows_all, "hrv_ms"), stats.series(rows_all, "resting_hr")

    def outcome(key: str, d: date) -> Optional[float]:
        morning = d + timedelta(days=1)
        row = body.get(morning) or {}
        if key == "asleep":
            return stats.minutes_since_noon(row["sleep_start"]) if row.get("sleep_start") and row.get("sleep_end") else None
        if key == "sleep_min":
            return row.get("sleep_min")
        values = hrv if key == "hrv" else rhr
        band = stats.typical(values, morning) if morning in values else None
        if band is None:
            return None
        return (values[morning] / band["median"] - 1) * 100 if key == "hrv" else values[morning] - band["median"]

    median = statistics.median(fun.values()) if len(fun) >= 2 * stats.MIN_GROUP_DAYS else None
    flags = {"fun_high": {d: v > median for d, v in fun.items()} if median is not None else {},
             "late_fun": {d: v > CALM_MIN for d, v in late.items()}}
    rows = []
    for exposure in EXPOSURES:
        for key in OUTCOMES:
            yes: List[float] = []
            no: List[float] = []
            for d, flag in flags[exposure].items():
                value = outcome(key, d)
                if value is not None:
                    (yes if flag else no).append(value)
            rows.append({"exposure": exposure, "outcome": key, "yes_days": len(yes), "no_days": len(no),
                         **stats.compare(yes, no)})
    tested = [r for r in rows if r["status"] == "ok"]
    for r, adjusted in zip(tested, stats.benjamini_hochberg([r["p"] for r in tested])):
        r["p_adjusted"] = adjusted
        r["detected"] = adjusted < stats.FDR
    return {"from": iso(first), "to": iso(last), "days": len(fun), "median_fun": median, "calm_min": CALM_MIN,
            "rows": rows, "better": OUTCOME_BETTER, "units": OUTCOME_UNITS,
            "method": {"min_group_days": stats.MIN_GROUP_DAYS, "fdr": stats.FDR}}


# ---- devices at once ---------------------------------------------------------------------------
def _stack(have: List[TimeDay]) -> Optional[Dict[str, Any]]:
    """Devices at once over the shown days whose screen record is whole: device minutes per hour, device
    and screen part, agent minutes taken out, and the single longest stretch on one thing."""
    days = [td for td in have if td.known["screen"] and td.stack is not None]
    if not days:
        return None
    n = len(days)
    devices: Dict[str, float] = {}
    hours: List[Dict[str, Dict[str, float]]] = [dict() for _ in range(24)]
    agent_hours = [0.0] * 24
    for td in days:
        st = td.stack
        for dev, m in st.by_device.items():
            devices[dev] = devices.get(dev, 0.0) + m / n
        for h in range(24):
            agent_hours[h] += st.agent_by_hour[h] / n
            for dev, parts in st.by_hour[h].items():
                slot = hours[h].setdefault(dev, {})
                for part, m in parts.items():
                    slot[part] = slot.get(part, 0.0) + m / n
    clock_hours = [sum(td.by_hour[h].get(p, 0.0) for td in days for p in SCREEN_PARTS) / n for h in range(24)]
    top = max(days, key=lambda td: (td.stack.single, td.day))
    st = top.stack
    best = None
    if st.single:
        start = st.single_start % 1440
        best = {"minutes": st.single, "app": st.single_app, "device": st.single_device, "date": iso(top.day),
                "start": f"{start // 60:02d}:{start % 60:02d}"}
    return {"n": n, "devices": devices, "by_hour": hours, "clock_by_hour": clock_hours, "agent_by_hour": agent_hours,
            "multi": sum(td.stack.multi for td in days) / n, "best_single": best}


def _stale(ctx: Context, time: Dict[date, TimeDay], span_to: date) -> List[Dict[str, Any]]:
    """Records that stop before the last shown day, with the last whole day that has one. For screens
    that is the day before the last imported one, which the import probably cut off (context.time_days)."""
    out = []
    for activity in STALE:
        last = max((d for d, td in time.items() if d < ctx.today and td.known[activity]), default=None)
        if last is None or last < span_to:
            out.append({"activity": activity, "last": iso(last)})
    return out


# ---- stimulation and focus, averaged ------------------------------------------------------------
# What people call "dopamine tolerance" cannot be measured by a phone or a watch. The card shows the
# behaviour around it instead, side by side and never as cause and effect: the minutes in entertainment
# and social apps, and the day's longest focus stretch.
TREND_DAYS = 90   # the card looks back this far
TREND_KEYS = ("fun", "longest_focus")
LEVEL_DAYS = 28   # the line above each chart: the daily average of the last 28 days and of the 28 before them,
LEVEL_MIN = 14    # each from at least this many days with screen time


def trend_series(ctx: Context) -> Dict[str, stats.Series]:
    """Daily values for the card, only on whole days with screen time: entertainment & social minutes
    (screens counted once across devices) and the longest focus stretch (context._longest: work and
    learning apps, a pause of up to STRETCH_GAP_MIN minutes does not end it). A day without screen time
    is missing, never zero."""
    time, screen = ctx.time_days(), ctx.screen_days()
    out: Dict[str, stats.Series] = {k: {} for k in TREND_KEYS}
    for d in data_days(ctx):
        fun = time[d].totals()["fun"]
        if fun is None or d not in screen:
            continue
        out["fun"][d] = fun
        out["longest_focus"][d] = screen[d].longest_focus
    return out


def _level(values: stats.Series, end: date) -> Dict[str, Any]:
    days = [end - timedelta(days=k) for k in range(LEVEL_DAYS)]
    have = [values[d] for d in days if d in values]
    return {"from": iso(days[-1]), "to": iso(end), "n": len(have),
            "avg": sum(have) / len(have) if len(have) >= LEVEL_MIN else None}


def trend(ctx: Context, last: date) -> Dict[str, Any]:
    """The TREND_DAYS days ending on ``last``. Per day: its value, the average of the 7 days ending on it
    (at least WEEK_MIN_DAYS of them with screen time) and your normal for that average (typical_week, the
    band the tiles use). Per measure: the daily average of the last LEVEL_DAYS days and of the LEVEL_DAYS
    before them."""
    first = last - timedelta(days=TREND_DAYS - 1)
    series = {}
    for key, values in trend_series(ctx).items():
        days = []
        for k in range(TREND_DAYS):
            d = first + timedelta(days=k)
            week = [values[d - timedelta(days=j)] for j in range(SPAN) if d - timedelta(days=j) in values]
            band = typical_week(values, d - timedelta(days=SPAN - 1))
            days.append({"date": iso(d), "value": values.get(d),
                         "avg7": sum(week) / len(week) if len(week) >= WEEK_MIN_DAYS else None,
                         "band": {"q1": band["q1"], "q3": band["q3"]} if band else None})
        series[key] = {"days": days, "recent": _level(values, last),
                       "before": _level(values, last - timedelta(days=LEVEL_DAYS))}
    return {"from": iso(first), "to": iso(last), "days": TREND_DAYS, "level_days": LEVEL_DAYS,
            "level_min": LEVEL_MIN, "series": series}


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
    series = stim_series(ctx)
    m = metrics(recent, series)
    have = [time[d] for d in recent]
    stack = _stack(have)
    if stack is not None:
        both = [d for d in recent if d in series["stacked"] and d in series["screen"]]
        stack.update(stacked=sum(series["stacked"][d] for d in both) / len(both) if both else None,
                     screen=sum(series["screen"][d] for d in both) / len(both) if both else None)
    normal_days = [d for d in series["fun"] if recent[0] - timedelta(days=stats.BASELINE_DAYS) <= d < recent[0]]
    limit = ctx.cfg.screen.entertainment_max_hours
    fun_known = [series["fun"][d] for d in recent if d in series["fun"]]
    # step by days with records, like "Earlier": the next page ends 7 such days later (or on the newest)
    later = [d for d in every if d > last]
    return {**base, "day": iso(last), "empty": False,
            "span": {"from": iso(recent[0]), "to": iso(last), "n": len(recent), "screen_days": len(fun_known),
                     "metrics": m, "level": level(m), "also": [k for k in STIM_KEYS[1:] if m[k]["clear"]],
                     "stale": _stale(ctx, time, last)},
            "plan": {"fun_max_min": limit * 60 if limit is not None else None,
                     "over": sum(1 for v in fun_known if limit is not None and v > limit * 60), "known": len(fun_known)},
            "hours": {"now": fun_hours(ctx, recent),
                      "normal": fun_hours(ctx, normal_days) if len(normal_days) >= stats.MIN_BASELINE else None,
                      "normal_days": len(normal_days)},
            "apps": fun_apps(ctx, [d for d in recent if d in series["fun"]]),
            "stack": stack, "response": response(ctx, last, series), "trend": trend(ctx, last),
            "baseline_days": stats.BASELINE_DAYS, "baseline_min": stats.MIN_BASELINE, "devices_order": ctx.cfg.devices,
            "limits": {"fun_max_min": limit * 60 if limit is not None else None},
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
