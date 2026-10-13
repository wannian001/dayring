"""Food: what you ate over the last 7 days against your normal and your plan, when the last meal came before
sleep, and whether the food log and the scale tell the same story.

Rules
- A meal before 4 am belongs to the day before (a night owl's midnight snack is that evening's, not breakfast).
  Exactly 00:00 is read as a date without a time (what a date-only export gives): it counts for its own day and
  leaves that day out of the last-meal timing.
- A day counts as logged once it has at least two main meals (breakfast, lunch, dinner). Food logs get skipped, and a
  day with one meal written down is not a day of eating one meal: it is shown, never averaged. A day with no rows is
  not logged (unknown, never zero calories). Today is not over: shown as "so far", never compared.
- Each number is the 7-day average over logged days (at least 3), against the middle half of the logged days in the
  28 days before (at least 8), and, where healthaio.toml sets one, against [plan.food].
- Last meal to sleep: hours from the start of the day's last meal to falling asleep that night (the sleep that ends
  the next morning). Under plan.food.last_meal_gap_h (3 by default) counts as a late meal, and two or more late nights
  in the 7 days are off the plan (judged night by night, never by the average). Only on logged days, so an unlogged
  late snack cannot make a day look early.
- Protein target: plan.food.protein_g, or protein_g_per_kg times the latest 7-day average weight.
- Energy balance: on logged days that also have the watch's energy burned (resting + active), eaten minus burned.
  Its 7-day average times 7, over 7,700 kcal per kg, is the weekly weight change the log implies; the Body page's
  weight trend is what the scale says. They seldom agree (logs miss food, watches estimate energy loosely), so the
  gap is shown as it is.
"""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import Context, iso
from ..schema import MAIN_MEALS
from . import body as body_page

WINDOW = 7
BASELINE = 28
MIN_WINDOW = 3
MIN_BASELINE = 8
WEEKS = 8
TIMELINE_DAYS = 14
KCAL_PER_KG = 7700.0
DAY_STARTS_HOUR = 4  # a meal before this belongs to the day before
NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")


def _sum(rows: List[Dict[str, Any]], key: str) -> Optional[float]:
    values = [r[key] for r in rows if r.get(key) is not None]
    return float(sum(values)) if values else None


def timed(moment) -> bool:
    """False for exactly 00:00, which is how a date-only export (one row per day or per meal) reads."""
    return bool(moment.hour or moment.minute)


def eating_day(moment) -> date:
    return (moment - timedelta(hours=DAY_STARTS_HOUR)).date() if timed(moment) else moment.date()


def food_days(ctx: Context, until: date) -> Dict[date, Dict[str, Any]]:
    """Every day up to ``until`` with at least one meal: its meals, totals, whether it counts, and the gap to sleep."""
    grouped: Dict[date, List[Dict[str, Any]]] = {}
    for row in ctx.store.rows("meals"):
        d = eating_day(row["time"])
        if d <= until:
            grouped.setdefault(d, []).append(row)
    body = ctx.store.by_date("body_daily")
    gap_h = ctx.cfg.food.last_meal_gap_h
    out: Dict[date, Dict[str, Any]] = {}
    for d, rows in grouped.items():
        rows.sort(key=lambda r: r["time"])
        main = len({r["meal"] for r in rows if r["meal"] in MAIN_MEALS})
        full = main >= 2 and d < ctx.today
        last = rows[-1]["time"]
        asleep = (body.get(d + timedelta(days=1)) or {}).get("sleep_start")
        # a meal without a clock time leaves the day out of the last-meal timing (it could have been the last)
        clocked = all(timed(r["time"]) for r in rows)
        gap = (asleep - last).total_seconds() / 3600 if full and clocked and asleep and asleep > last else None
        out[d] = {"date": d, "meals": rows, "main": main, "full": full, "first": rows[0]["time"], "last": last,
                  "asleep": asleep, "gap_h": gap, "late": None if gap is None else gap < gap_h,
                  **{k: _sum(rows, k) for k in NUTRIENTS}}
    return out


def protein_target(ctx: Context, day: date) -> Dict[str, Any]:
    plan = ctx.cfg.food
    if plan.protein_g is not None:
        return {"grams": plan.protein_g, "per_kg": None, "weight_kg": None}
    if plan.protein_g_per_kg is None:
        return {"grams": None, "per_kg": None, "weight_kg": None}
    weights = {r["date"]: r["weight_kg"] for r in ctx.store.rows("body_daily")
               if r.get("weight_kg") is not None and r["date"] <= day}
    latest = None
    for d in sorted(weights, reverse=True):
        latest = body_page.avg7(weights, d) or weights[d]
        break
    return {"grams": plan.protein_g_per_kg * latest if latest else None, "per_kg": plan.protein_g_per_kg,
            "weight_kg": latest}


def _band(values: List[float]) -> Optional[Dict[str, float]]:
    if len(values) < MIN_BASELINE:
        return None
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"q1": q1, "median": median, "q3": q3, "days": len(values)}


def _plan_state(value: Optional[float], low: Optional[float], high: Optional[float]) -> Optional[str]:
    if value is None or (low is None and high is None):
        return None
    if low is not None and value < low:
        return "below"
    if high is not None and value > high:
        return "above"
    return "within"


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    latest = ctx.today - timedelta(days=1)  # today is not over
    end = min(date.fromisoformat(day) if day else latest, latest)
    window = [end - timedelta(days=k) for k in range(WINDOW)]
    base = [end - timedelta(days=WINDOW + k) for k in range(BASELINE)]
    days = food_days(ctx, max(end, ctx.today))
    logged = {d: x for d, x in days.items() if x["full"]}
    plan = ctx.cfg.food
    protein = protein_target(ctx, end)
    gap_plan = plan.last_meal_gap_h

    def series(key: str) -> stats.Series:
        return {d: x[key] for d, x in logged.items() if x.get(key) is not None}

    def row(key: str, unit: str, better: str, values: stats.Series, low=None, high=None) -> Dict[str, Any]:
        inside = [values[d] for d in window if d in values]
        past = [values[d] for d in base if d in values]
        value = statistics.fmean(inside) if len(inside) >= MIN_WINDOW else None
        band = _band(past)
        state = stats.classify(value, band)
        weeks = []
        for w in range(WEEKS - 1, -1, -1):
            block = [values[end - timedelta(days=7 * w + k)] for k in range(WINDOW) if end - timedelta(days=7 * w + k) in values]
            weeks.append({"to": iso(end - timedelta(days=7 * w)), "value": statistics.fmean(block) if len(block) >= MIN_WINDOW else None})
        plan_state = _plan_state(value, low, high)
        return {"key": key, "unit": unit, "better": better, "value": value, "band": band, "state": state,
                "tone": stats.tone(state, better), "days": len(inside), "weeks": weeks,
                "plan": {"low": low, "high": high} if low is not None or high is not None else None,
                "plan_state": plan_state,
                "plan_tone": None if plan_state is None else ("good" if plan_state == "within" else "bad"),
                "series": [{"date": iso(d), "value": values.get(d)} for d in sorted(window + base)]}

    gaps = {d: x["gap_h"] for d, x in logged.items() if x["gap_h"] is not None}
    rows = [
        row("kcal", "kcal", "none", series("kcal"), plan.kcal_min, plan.kcal_max),
        row("protein_g", "g", "higher", series("protein_g"), protein["grams"]),
        row("gap_h", "h", "higher", gaps, gap_plan),
        row("fiber_g", "g", "higher", series("fiber_g")),
    ]
    late_days = [d for d in window if d in gaps and gaps[d] < gap_plan]
    known_gap = [d for d in window if d in gaps]
    # the last meal is judged night by night, not by its average: two or more late nights are off the plan
    gap_row = rows[2]
    if gap_row["value"] is not None:
        gap_row["plan_state"] = "below" if len(late_days) >= 2 else "within"
        gap_row["plan_tone"] = "bad" if len(late_days) >= 2 else "good"
        gap_row["late"] = {"days": len(late_days), "known": len(known_gap)}

    timeline = []
    body = ctx.store.by_date("body_daily")
    for k in range(TIMELINE_DAYS - 1, -1, -1):
        d = ctx.today - timedelta(days=k)
        x = days.get(d)
        wake = (body.get(d) or {}).get("sleep_end")
        asleep = (body.get(d + timedelta(days=1)) or {}).get("sleep_start")
        timeline.append({
            "date": iso(d), "status": "none" if x is None else ("today" if d == ctx.today else "full" if x["full"] else "partial"),
            "wake": iso(wake), "asleep": iso(asleep) if d < ctx.today else None,
            "kcal": x["kcal"] if x else None, "protein_g": x["protein_g"] if x else None,
            "gap_h": x["gap_h"] if x else None, "late": x["late"] if x else None,
            "meals": [{"time": iso(m["time"]), "meal": m["meal"], "title": m.get("title"), "kcal": m.get("kcal"),
                       "protein_g": m.get("protein_g")} for m in (x["meals"] if x else [])]})

    # energy balance: eaten minus burned on logged days with both, against the scale
    eaten_burned = []
    for d in window:
        x, b = logged.get(d), body.get(d) or {}
        if x and x["kcal"] is not None and b.get("active_kcal") is not None and b.get("basal_kcal") is not None:
            eaten_burned.append((x["kcal"], b["active_kcal"] + b["basal_kcal"]))
    balance = None
    if len(eaten_burned) >= MIN_WINDOW:
        intake = statistics.fmean(e for e, _ in eaten_burned)
        burned = statistics.fmean(b for _, b in eaten_burned)
        weight = body_page.build(ctx, iso(end))["latest"]
        balance = {"days": len(eaten_burned), "intake": intake, "burned": burned, "diff": intake - burned,
                   "implied_kg_week": (intake - burned) * 7 / KCAL_PER_KG,
                   "scale_kg_week": weight["rate_per_week"], "scale_date": weight["date"]}

    macros = None
    window_logged = [logged[d] for d in window if d in logged]
    if len(window_logged) >= MIN_WINDOW and all(x[k] is not None for x in window_logged for k in ("protein_g", "carbs_g", "fat_g")):
        grams = {k: statistics.fmean(x[k] for x in window_logged) for k in ("protein_g", "carbs_g", "fat_g")}
        energy = {"protein_g": grams["protein_g"] * 4, "carbs_g": grams["carbs_g"] * 4, "fat_g": grams["fat_g"] * 9}
        total = sum(energy.values()) or 1.0
        macros = [{"key": k, "grams": grams[k], "share": energy[k] / total} for k in ("protein_g", "carbs_g", "fat_g")]

    from . import today as today_page  # the same next-day comparison the Today page lists
    effects = today_page.effects(ctx, end + timedelta(days=1))
    effect = {name: next((r for r in rows_ if r["key"] == "ate_early"), None) for name, rows_ in effects["rows"].items()}

    so_far = days.get(ctx.today)
    off = [r["key"] for r in rows if r["plan_tone"] == "bad"]
    return {
        "page": "food", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
        "window": {"from": iso(window[-1]), "to": iso(end)},
        "plan": {"kcal_min": plan.kcal_min, "kcal_max": plan.kcal_max, "protein_g": protein["grams"],
                 "protein_g_per_kg": protein["per_kg"], "weight_kg": protein["weight_kg"], "last_meal_gap_h": gap_plan,
                 "set": any(v is not None for v in (plan.kcal_min, plan.kcal_max, protein["grams"]))},
        "logged": {"full": sum(1 for d in window if d in logged), "partial": sum(1 for d in window if d in days and d not in logged),
                   "days": WINDOW, "ever": bool(days)},
        "rows": rows, "off": off, "worse": [r["key"] for r in rows if r["tone"] == "bad"],
        "late": {"days": len(late_days), "known": len(known_gap), "gap_h": gap_plan},
        "timeline": timeline, "balance": balance, "macros": macros, "effect": effect,
        "effect_days": effects["method"]["min_group_days"],
        "so_far": {"kcal": so_far["kcal"], "protein_g": so_far["protein_g"], "meals": len(so_far["meals"])} if so_far else None,
        "prev": iso(end - timedelta(days=WINDOW)),
        "next": iso(min(end + timedelta(days=WINDOW), latest)) if end < latest else None, "latest": iso(latest),
        "rule": {"window": WINDOW, "baseline": BASELINE, "min_window": MIN_WINDOW, "min_baseline": MIN_BASELINE,
                 "kcal_per_kg": KCAL_PER_KG, "day_starts": DAY_STARTS_HOUR},
    }


def late_meal_flags(ctx: Context, until: date) -> Dict[date, float]:
    """1.0 when the last meal of a logged day started at least plan.food.last_meal_gap_h before falling asleep, else
    0.0; days without a full log or a sleep that night are left out (unknown)."""
    gap_h = ctx.cfg.food.last_meal_gap_h
    return {d: float(x["gap_h"] >= gap_h) for d, x in food_days(ctx, until).items() if x["gap_h"] is not None}
