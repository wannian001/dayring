"""Review: one week of facts next to the four weeks before it. Facts only; the judging is yours."""
import statistics
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from .. import stats
from ..context import FOCUS, FUN, Context, iso
from . import exercise as exercise_page
from . import food as food_page
from .week import monday


def _summary(values: List[float], how: str) -> Optional[float]:
    if not values:
        return None
    return statistics.median(values) if how == "median" else statistics.fmean(values)


def build(ctx: Context, week: Optional[str] = None) -> Dict[str, Any]:
    start = monday(date.fromisoformat(week) if week else ctx.today - timedelta(days=1))
    end = start + timedelta(days=6)
    body = ctx.store.by_date("body_daily")
    screen = ctx.screen_days()
    selfr = ctx.store.by_date("self_report")
    complete = lambda d: (body.get(d) or {}).get("complete") is not False

    def days(offset_weeks: int, span_weeks: int = 1) -> List[date]:
        first = start - timedelta(days=7 * offset_weeks)
        return [first + timedelta(days=k) for k in range(7 * span_weeks) if first + timedelta(days=k) <= ctx.today]

    this, before = days(0), days(4, 4)

    def metric(key: str, unit: str, better: str, pick: Callable[[date], Optional[float]], how: str = "mean") -> Dict[str, Any]:
        a = [v for v in (pick(d) for d in this) if v is not None]
        b = [v for v in (pick(d) for d in before) if v is not None]
        va, vb = _summary(a, how), _summary(b, how)
        return {"key": key, "unit": unit, "better": better, "how": how, "value": va, "before": vb,
                "change": (va - vb) if va is not None and vb is not None else None, "days": len(a), "before_days": len(b),
                "points": [{"date": iso(d), "value": pick(d)} for d in this]}

    col = lambda name: (lambda d: (body.get(d) or {}).get(name))
    onset = lambda d: stats.minutes_since_noon(body[d]["sleep_start"]) if (body.get(d) or {}).get("sleep_start") else None
    wake = lambda d: stats.minutes_of_day(body[d]["sleep_end"]) if (body.get(d) or {}).get("sleep_end") else None
    whole = lambda name: (lambda d: (body.get(d) or {}).get(name) if complete(d) else None)

    def exercise(d: date) -> Optional[float]:
        """Workout minutes by the day ring's rule (context.exercise_on); None for today and for days with no workout record."""
        return ctx.exercise_on(d) if d < ctx.today else None

    active = exercise_page.active_minutes(ctx, ctx.today - timedelta(days=1))
    eaten = {d: x for d, x in food_page.food_days(ctx, end).items() if x["full"]}
    ate = lambda key: (lambda d: (eaten.get(d) or {}).get(key))

    sections = [
        {"key": "sleep", "metrics": [metric("sleep_min", "min", "higher", col("sleep_min")),
                                     metric("onset", "clock", "none", onset), metric("wake", "clock_day", "none", wake)]},
        {"key": "recovery", "metrics": [metric("hrv_ms", "ms", "higher", col("hrv_ms"), "median"),
                                        metric("resting_hr", "bpm", "lower", col("resting_hr"), "median")]},
        {"key": "activity", "metrics": [metric("steps", "steps", "none", whole("steps")),
                                        metric("active_min", "min", "higher", lambda d: active.get(d)),
                                        metric("workout_min", "min", "higher", exercise),
                                        metric("workout_days", "days", "none",
                                               lambda d: None if exercise(d) is None else float(exercise(d) > 0))]},
        {"key": "screens", "metrics": [metric("focus", "min", "higher", lambda d: screen[d].share(FOCUS) if d in screen and d < ctx.today else None),
                                         metric("fun", "min", "lower", lambda d: screen[d].share(FUN) if d in screen and d < ctx.today else None)]},
        {"key": "food", "metrics": [metric("kcal", "kcal", "none", ate("kcal")), metric("protein_g", "g", "higher", ate("protein_g")),
                                    metric("gap_h", "h", "higher", ate("gap_h")),
                                    metric("logged_days", "days", "none", lambda d: None if d >= ctx.today else float(d in eaten))]},
        {"key": "self", "metrics": [metric("energy", "points", "higher", lambda d: (selfr.get(d) or {}).get("energy")),
                                    metric("focus_self", "points", "higher", lambda d: (selfr.get(d) or {}).get("focus"))]},
    ]
    # workouts are a count for the week, not an average
    for m in sections[2]["metrics"]:
        if m["key"] == "workout_days":
            m["value"] = sum(1 for p in m["points"] if p["value"]) if m["days"] else None
            # weeks before: only weeks where every day's workouts are known, so a gap is not a rest week
            weekly = []
            for w in range(1, 5):
                week_days = [start - timedelta(days=7 * w) + timedelta(days=k) for k in range(7)]
                values = [exercise(d) for d in week_days]
                if all(v is not None for v in values):
                    weekly.append(sum(1 for v in values if v > 0))
            m["before"] = statistics.fmean(weekly) if weekly else None
            m["before_days"] = 7 * len(weekly)
            m["change"] = m["value"] - m["before"] if m["before"] is not None and m["days"] else None
    # days logged in full: a count for the week (against the average week before), like training days
    food = next(x for x in sections if x["key"] == "food")
    if not ctx.store.load("meals").present:
        sections.remove(food)  # someone who does not log food gets no empty section
    else:
        m = next(x for x in food["metrics"] if x["key"] == "logged_days")
        m["value"] = sum(1 for p in m["points"] if p["value"]) if m["days"] else None
        weekly = [sum(1 for k in range(7) if start - timedelta(days=7 * w) + timedelta(days=k) in eaten) for w in range(1, 5)]
        m["before"] = statistics.fmean(weekly)
        m["before_days"] = 28
        m["change"] = m["value"] - m["before"] if m["value"] is not None else None
    planned = len(ctx.cfg.training)
    weights = {d: (body.get(d) or {}).get("weight_kg") for d in this}
    w_now = [v for v in weights.values() if v is not None]
    w_prev = [v for v in ((body.get(d - timedelta(days=7)) or {}).get("weight_kg") for d in this) if v is not None]
    deadlines = ctx.store.rows("deadlines")
    due_this = [{"due": iso(x["due"]), "title": x["title"], "group": x.get("group"), "weight_pct": x.get("weight_pct"),
                 "status": x.get("status") or "todo"} for x in deadlines if start <= x["due"].date() <= end]
    due_next = [{"due": iso(x["due"]), "title": x["title"], "group": x.get("group"), "weight_pct": x.get("weight_pct"),
                 "status": x.get("status") or "todo"} for x in deadlines
                if end < x["due"].date() <= end + timedelta(days=7)]
    gaps = [iso(d) for d in this if d not in body or (body[d].get("sleep_min") is None and body[d].get("hrv_ms") is None)]
    # what has tended to help the next day, over your whole history up to the end of this week (moved here from Today:
    # it is a pattern across weeks, read when looking back, not a number for the morning)
    from . import today as today_page
    effects = today_page.effects(ctx, min(end, ctx.today))
    return {"page": "review", "week_start": iso(start), "week_end": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
            "partial": end >= ctx.today, "sections": sections, "planned_workouts": planned,
            "weight": {"avg": statistics.fmean(w_now) if w_now else None,
                       "prev_avg": statistics.fmean(w_prev) if w_prev else None, "days": len(w_now)},
            "due_this": sorted(due_this, key=lambda x: x["due"]), "due_next": sorted(due_next, key=lambda x: x["due"]),
            "gaps": gaps, "effects": effects, "prev": iso(start - timedelta(days=7)),
            "next": iso(start + timedelta(days=7)) if start + timedelta(days=7) <= ctx.today else None}
