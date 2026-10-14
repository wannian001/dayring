"""Recovery (#recovery): how recovered you are, what your training has asked of you, where you are sore, and how
your body has answered training.

- How recovered: the Today page's own verdict (HRV, resting heart rate and last night's sleep against your normal;
  two of three worse = below your normal), so both pages always agree.
- Training load: each workout's effort on Apple's 1-10 scale (your rating in the Fitness or Workout app, else the
  watch's estimate; workouts.csv `effort`) times its minutes, summed per day. This is the session-RPE method from
  sport science (Foster et al. 2001), and the same idea as Apple Fitness's own Training Load. The last 7 days
  (today so far included) are set against the weekly average of the 28 days before them: above 1.3 times reads as
  more than you are used to, below 0.8 as less (the Exercise page's minutes-only load uses the same lines).
  Workout minutes without an effort score are left out and counted; with under half of the minutes rated the load
  says it is unsure. A day with no workout, inside the range the workout record covers, is a load of 0.
  No device measures how tired the nervous system is. The load is what the training asked of you, as you (or the
  watch) judged it; the next morning's HRV and resting heart rate are the autonomic nervous system's answer.
- How the body answered (response): over the last RESPONSE_DAYS days, the next morning after hard days (load above
  the median of your training days) against every other known day (easier days and rest days): HRV in percent and
  resting heart rate in beats against your normal that morning, and, where you checked in, the most sore region's
  level. Difference of means with a 95% interval, at least stats.MIN_GROUP_DAYS days a side, Benjamini-Hochberg
  across the three; only what survives is a difference. An association, not a cause.
- Soreness: the morning check-ins in soreness.csv (1 a little, 2 clearly sore, 3 very sore, per region of the body
  figure). The figure shows the latest check-in; the last SORE_DAYS days show each region's levels. A day without a
  check-in is unknown, never "not sore".
"""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import Context, iso
from ..schema import SORE_REGIONS
from . import today as today_page

ACUTE = 7
CHRONIC = 28
CHART_DAYS = 42
LOAD_HIGH, LOAD_LOW = 1.3, 0.8
MIN_RATED_SHARE = 0.5
SORE_DAYS = 14
RESPONSE_DAYS = 90
OUTCOMES = ("hrv", "resting_hr", "sore_max")
OUTCOME_BETTER = {"hrv": "higher", "resting_hr": "lower", "sore_max": "lower"}
OUTCOME_UNITS = {"hrv": "%", "resting_hr": "bpm", "sore_max": "level"}


def daily_load(ctx: Context, until: date) -> Dict[date, Dict[str, Any]]:
    """Every day from the first workout on record to ``until`` that the workout record covers: its load (effort x
    minutes, rated minutes only), its workout minutes, how many of them had an effort, and the sessions."""
    rows = [w for w in ctx.store.rows("workouts") if w["end"] > w["start"] and w["start"].date() <= until]
    out: Dict[date, Dict[str, Any]] = {}
    if not rows:
        return out
    d = min(w["start"].date() for w in rows)
    while d <= until:
        if ctx.exercise_on(d) is not None or any(w["start"].date() == d for w in rows):
            out[d] = {"load": 0.0, "minutes": 0.0, "rated_min": 0.0, "sessions": []}
        d += timedelta(days=1)
    for w in sorted(rows, key=lambda r: r["start"]):
        day = out.get(w["start"].date())
        if day is None:
            continue
        minutes = (w["end"] - w["start"]).total_seconds() / 60
        day["minutes"] += minutes
        if w.get("effort") is not None:
            day["load"] += w["effort"] * minutes
            day["rated_min"] += minutes
        last = day["sessions"][-1] if day["sessions"] else None
        if last and last["type"] == w["type"] and last["effort"] == w.get("effort"):  # stretches of one paused workout
            last["minutes"] += minutes
        else:
            day["sessions"].append({"type": w["type"], "start": iso(w["start"]), "minutes": minutes,
                                    "effort": w.get("effort"), "effort_source": w.get("effort_source")})
    return out


def load_summary(days: Dict[date, Dict[str, Any]], end: date) -> Dict[str, Any]:
    acute_days = [end - timedelta(days=k) for k in range(ACUTE)]
    base_days = [end - timedelta(days=ACUTE + k) for k in range(CHRONIC)]
    acute = sum(days[d]["load"] for d in acute_days if d in days)
    known_base = [d for d in base_days if d in days]
    chronic = sum(days[d]["load"] for d in known_base) / (CHRONIC / ACUTE) if len(known_base) >= 21 else None
    minutes = sum(days[d]["minutes"] for d in acute_days + base_days if d in days)
    rated = sum(days[d]["rated_min"] for d in acute_days + base_days if d in days)
    share = rated / minutes if minutes else None
    ratio = acute / chronic if chronic else None
    if not minutes:
        state = "none"
    elif share is not None and share < MIN_RATED_SHARE:
        state = "few_ratings"
    elif ratio is None:
        state = "unknown"
    else:
        state = "high" if ratio > LOAD_HIGH else "low" if ratio < LOAD_LOW else "steady"
    unrated = sum(days[d]["minutes"] - days[d]["rated_min"] for d in acute_days if d in days)
    return {"acute": acute, "chronic": chronic, "ratio": ratio, "state": state, "rated_share": share,
            "unrated_min": unrated, "known_base": len(known_base), "high": LOAD_HIGH, "low": LOAD_LOW}


def soreness_log(ctx: Context) -> Dict[date, Dict[str, int]]:
    """Each checked-in morning as {region: level}; an empty dict is a check-in with nothing sore."""
    out: Dict[date, Dict[str, int]] = {}
    for row in ctx.store.rows("soreness"):
        day = out.setdefault(row["date"], {})
        if row["region"] != "none" and row["level"]:
            day[row["region"]] = int(row["level"])
    return out


def soreness(ctx: Context, end: date, log: Dict[date, Dict[str, int]]) -> Dict[str, Any]:
    latest = max((d for d in log if d <= end), default=None)
    days = [end - timedelta(days=k) for k in range(SORE_DAYS - 1, -1, -1)]
    checked = [d for d in days if d in log]
    regions = []
    for region in SORE_REGIONS:
        levels = [log[d].get(region, 0) for d in checked]
        regions.append({"key": region, "days": [{"date": iso(d), "level": log[d].get(region, 0) if d in log else None} for d in days],
                        "sore_days": sum(1 for v in levels if v), "max": max(levels, default=0)})
    return {"latest": iso(latest), "today": latest == end, "levels": log.get(latest, {}) if latest else {},
            "checked": len(checked), "days": SORE_DAYS, "regions": regions}


def response(ctx: Context, end: date, days: Dict[date, Dict[str, Any]], log: Dict[date, Dict[str, int]]) -> Dict[str, Any]:
    """The next morning after hard days against the other known days (see the module's docstring)."""
    first = end - timedelta(days=RESPONSE_DAYS - 1)
    window = {d: v for d, v in days.items() if first <= d <= end and v["minutes"] == v["rated_min"]}  # fully rated
    trained = [v["load"] for v in window.values() if v["load"] > 0]
    median = statistics.median(trained) if len(trained) >= stats.MIN_GROUP_DAYS else None
    rows_all = [r for r in ctx.store.rows("body_daily") if r.get("complete") is not False]
    hrv, rhr = stats.series(rows_all, "hrv_ms"), stats.series(rows_all, "resting_hr")

    def outcome(key: str, d: date) -> Optional[float]:
        morning = d + timedelta(days=1)
        if key == "sore_max":
            return float(max(log[morning].values(), default=0)) if morning in log else None
        values = hrv if key == "hrv" else rhr
        band = stats.typical(values, morning) if morning in values else None
        if band is None:
            return None
        return (values[morning] / band["median"] - 1) * 100 if key == "hrv" else values[morning] - band["median"]

    rows = []
    for key in OUTCOMES:
        yes: List[float] = []
        no: List[float] = []
        if median is not None:
            for d, v in window.items():
                value = outcome(key, d)
                if value is not None:
                    (yes if v["load"] > median else no).append(value)
        rows.append({"outcome": key, "yes_days": len(yes), "no_days": len(no), **stats.compare(yes, no)})
    tested = [r for r in rows if r["status"] == "ok"]
    for r, adjusted in zip(tested, stats.benjamini_hochberg([r["p"] for r in tested])):
        r["p_adjusted"] = adjusted
        r["detected"] = adjusted < stats.FDR
    return {"from": iso(first), "to": iso(end), "median_load": median, "training_days": len(trained), "rows": rows,
            "better": OUTCOME_BETTER, "units": OUTCOME_UNITS,
            "method": {"min_group_days": stats.MIN_GROUP_DAYS, "fdr": stats.FDR}}


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    end = min(date.fromisoformat(day) if day else ctx.today, ctx.today)
    days = daily_load(ctx, end)
    log = soreness_log(ctx)
    chart = [end - timedelta(days=k) for k in range(CHART_DAYS - 1, -1, -1)]
    return {"page": "recovery", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now), "figure": ctx.cfg.figure,
            "recovery": today_page.recovery(ctx, end),
            "load": load_summary(days, end),
            "load_days": [{"date": iso(d), **({"load": days[d]["load"], "minutes": days[d]["minutes"],
                                               "rated_min": days[d]["rated_min"], "sessions": days[d]["sessions"]}
                                              if d in days else {"load": None})} for d in chart],
            "soreness": soreness(ctx, end, log),
            "response": response(ctx, end, days, log),
            "regions": list(SORE_REGIONS),
            "rule": {"acute": ACUTE, "chronic": CHRONIC, "min_rated": MIN_RATED_SHARE, "sore_days": SORE_DAYS,
                     "response_days": RESPONSE_DAYS}}
