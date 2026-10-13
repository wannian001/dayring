"""Drain: the quiet things that wear you down, over the last 7 days.

Seven signals, named the way physiology and sleep research name them, each with one line on why it matters:
resting heart rate (high = sympathetic load, worse recovery), HRV (low = less vagal tone), the time you fall
asleep (later pushes the body clock back), sleep-timing spread (the body clock not lining up from night to night),
screen in the hour before sleep (light and stimulation delay sleep), entertainment & social (dense,
high-reward input; softer evidence), and app switches per screen hour (fragmented attention).

Two separate judgements, never mixed into a score:
- Against your normal: the 7-day average against the middle half of the 28 days before (sleep-timing
  spread against the range of the four 7-night blocks before). Out of the band in the worse direction = worse.
  If your normal was already bad, this says "within normal"; that is what the plan comparison is for.
- Against your plan, only where healthaio.toml sets one: falling asleep against plan.sleep.bedtime,
  entertainment & social against plan.screen.entertainment_max_hours.
Plus one stack-up check: short nights and hard training in the same week.
"""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import FUN, Context, iso
from . import today as today_page

WINDOW = 7
BASELINE = 28
MIN_WINDOW = 4
MIN_BASELINE = 10
WEEKS = 8
MIN_SCREEN_FOR_SWITCHES = 60  # minutes; fewer and the per-hour rate is noise
BEFORE_SLEEP = 60  # minutes before falling asleep

# key, worse direction, unit
ITEMS = (("resting_hr", "high", "bpm"), ("hrv", "low", "ms"), ("asleep", "high", "clock"),
         ("spread", "high", "min"), ("before_sleep", "high", "min"), ("fun", "high", "min"),
         ("switches", "high", "per_hour"))


def daily_series(ctx: Context, end: date) -> Dict[str, stats.Series]:
    """Each signal as a value per day, using only days its own source recorded (missing is never zero).

    A screen day counts only when its record is whole (Context.screen_known_days: before today, and not
    the last day of an import that has stopped arriving, which was most likely cut off part-way)."""
    body = [r for r in ctx.store.rows("body_daily") if r["date"] <= end]
    out: Dict[str, stats.Series] = {"resting_hr": stats.series(body, "resting_hr"), "hrv": stats.series(body, "hrv_ms")}
    out["asleep"] = {r["date"]: stats.minutes_since_noon(r["sleep_start"]) for r in body
                     if r.get("sleep_start") and r.get("sleep_end")}
    known = ctx.screen_known_days()
    screen = {d: sd for d, sd in known.items() if d <= end}
    out["fun"] = {d: sd.share(FUN) for d, sd in screen.items()}
    before: stats.Series = {}
    for r in body:
        start = r.get("sleep_start")
        if not start:
            continue
        hour = start - timedelta(minutes=BEFORE_SLEEP)
        if hour.date() not in known or (start - timedelta(minutes=1)).date() not in known:
            continue  # part of that hour sits on a day without a whole screen record: unknown, not 0
        minutes = 0
        t = hour
        while t < start:
            if (t.hour * 60 + t.minute) in known[t.date()].minutes:
                minutes += 1
            t += timedelta(minutes=1)
        before[r["date"]] = float(minutes)
    out["before_sleep"] = before
    # one count per session; the same session imported under two device names (two Macs sharing one data
    # folder) is counted once, as screen time itself counts each minute once across devices
    sessions: Dict[date, int] = {}
    seen = set()
    for row in ctx.store.rows("screen_sessions"):
        key = (row["start"], row["end"], row["app"])
        if key in seen:
            continue
        seen.add(key)
        sessions[row["start"].date()] = sessions.get(row["start"].date(), 0) + 1
    out["switches"] = {d: sessions.get(d, 0) / (sd.total / 60) for d, sd in screen.items()
                       if sd.total >= MIN_SCREEN_FOR_SWITCHES}
    return out


def _midpoints(ctx: Context, days: List[date]) -> List[float]:
    body = ctx.store.by_date("body_daily")
    out = []
    for d in days:
        r = body.get(d) or {}
        if r.get("sleep_start") and r.get("sleep_end"):
            start = stats.minutes_since_noon(r["sleep_start"])
            out.append(start + (r["sleep_end"] - r["sleep_start"]).total_seconds() / 120)
    return out


def _spread(ctx: Context, days: List[date]) -> Optional[float]:
    mids = _midpoints(ctx, days)
    return statistics.pstdev(mids) if len(mids) >= MIN_WINDOW else None


def _plan(ctx: Context, key: str) -> Optional[Dict[str, Any]]:
    cfg = ctx.cfg
    if key == "asleep" and cfg.sleep.bedtime is not None:
        return {"limit": stats.minutes_since_noon(cfg.sleep.bedtime), "kind": "bedtime",
                "clock": cfg.sleep.bedtime.strftime("%H:%M")}
    if key == "fun" and cfg.screen.entertainment_max_hours is not None:  # 0 h is a plan too
        return {"limit": cfg.screen.entertainment_max_hours * 60, "kind": "limit"}
    return None


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    latest = ctx.today - timedelta(days=1)  # today is not over
    end = min(date.fromisoformat(day) if day else latest, latest)
    window = [end - timedelta(days=k) for k in range(WINDOW)]
    base = [end - timedelta(days=WINDOW + k) for k in range(BASELINE)]
    series = daily_series(ctx, end)
    rows = []
    for key, worse, unit in ITEMS:
        if key == "spread":
            value = _spread(ctx, window)
            chunks = [c for c in (_spread(ctx, base[k:k + WINDOW]) for k in range(0, BASELINE, WINDOW)) if c is not None]
            band = {"q1": min(chunks), "q3": max(chunks), "median": statistics.median(chunks), "days": len(chunks) * WINDOW} \
                if len(chunks) >= 2 else None
            weeks = [{"to": iso(end - timedelta(days=7 * w)),
                      "value": _spread(ctx, [end - timedelta(days=7 * w + k) for k in range(WINDOW)])} for w in range(WEEKS - 1, -1, -1)]
            have = len(_midpoints(ctx, window))
        else:
            values = series[key]
            inside = [values[d] for d in window if d in values]
            past = [values[d] for d in base if d in values]
            value = statistics.fmean(inside) if len(inside) >= MIN_WINDOW else None
            band = None
            if len(past) >= MIN_BASELINE:
                q1, median, q3 = statistics.quantiles(past, n=4, method="inclusive")
                band = {"q1": q1, "median": median, "q3": q3, "days": len(past)}
            weeks = []
            for w in range(WEEKS - 1, -1, -1):
                block = [values[end - timedelta(days=7 * w + k)] for k in range(WINDOW) if end - timedelta(days=7 * w + k) in values]
                weeks.append({"to": iso(end - timedelta(days=7 * w)), "value": statistics.fmean(block) if len(block) >= MIN_WINDOW else None})
            have = len(inside)
        state = stats.classify(value, band)
        tone = "neutral" if state in (None, "normal") else ("bad" if state == worse else "good")
        row = {"key": key, "unit": unit, "worse": worse, "value": value, "band": band, "state": state, "tone": tone,
               "days": have, "weeks": weeks}
        plan = _plan(ctx, key)
        if plan:
            row["plan"] = plan
            if value is not None:
                over = value - plan["limit"]
                row["plan_over"] = over
                row["plan_tone"] = "bad" if over > 0 else "good"
        rows.append(row)
    return {"page": "drain", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
            "window": {"from": iso(window[-1]), "to": iso(end)}, "rows": rows,
            "worse": [r["key"] for r in rows if r["tone"] == "bad"],
            "plan_off": [r["key"] for r in rows if r.get("plan_tone") == "bad"],
            "strain": today_page.week_load(ctx, end),
            "prev": iso(end - timedelta(days=WINDOW)),
            # a window off the 7-day grid (a link from a past Today) can still step forward, ending on the latest
            "next": iso(min(end + timedelta(days=WINDOW), latest)) if end < latest else None,
            "latest": iso(latest),
            "compared": sum(1 for r in rows if r["value"] is not None and r["band"]),
            "rule": {"window": WINDOW, "baseline": BASELINE, "min_window": MIN_WINDOW, "min_baseline": MIN_BASELINE}}

