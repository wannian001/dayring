"""Body: weight against the plan's corridor, the weekly rate, and the long view."""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ..context import Context, iso

CHART_DAYS = 120
OUTLIER = 0.15  # a weight more than 15% off the median of all weights is ignored as a typo or another person


def avg7(points: Dict[date, float], day: date) -> Optional[float]:
    vals = [points[day - timedelta(days=k)] for k in range(7) if day - timedelta(days=k) in points]
    return statistics.fmean(vals) if len(vals) >= 3 else None


def slope_per_week(series: Dict[date, float], end: date, days: int = 21) -> Optional[float]:
    pts = [(d, v) for d, v in series.items() if end - timedelta(days=days) < d <= end]
    if len(pts) < 6:
        return None
    xs = [(d - end).days for d, _ in pts]
    ys = [v for _, v in pts]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * 7


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    end = date.fromisoformat(day) if day else ctx.today
    rows = [r for r in ctx.store.rows("body_daily") if r["date"] <= end]
    raw = {r["date"]: r["weight_kg"] for r in rows if r.get("weight_kg") is not None}
    dropped: List[str] = []
    if raw:
        median = statistics.median(raw.values())
        for d in list(raw):
            if abs(raw[d] / median - 1) > OUTLIER:
                dropped.append(iso(d))
                del raw[d]
    smooth = {d: v for d, v in ((d, avg7(raw, d)) for d in sorted(raw)) if v is not None}
    start = end - timedelta(days=CHART_DAYS - 1)
    plan = ctx.cfg.weight
    corridor = []
    status = None
    if plan:
        fast, slow = max(plan.weekly_loss_pct) / 100, min(plan.weekly_loss_pct) / 100
        d = max(plan.start_date, start)
        while d <= end + timedelta(days=14):
            weeks = (d - plan.start_date).days / 7
            corridor.append({"date": iso(d), "low": max(plan.target_kg, plan.start_kg * (1 - fast) ** weeks),
                             "high": max(plan.target_kg, plan.start_kg * (1 - slow) ** weeks)})
            d += timedelta(days=1)
    latest_day = max(smooth) if smooth else None
    latest = smooth.get(latest_day) if latest_day else None
    rate = slope_per_week(smooth, latest_day) if latest_day else None
    if plan and latest is not None and plan.start_date <= latest_day:
        weeks = (latest_day - plan.start_date).days / 7
        low = plan.start_kg * (1 - max(plan.weekly_loss_pct) / 100) ** weeks
        high = plan.start_kg * (1 - min(plan.weekly_loss_pct) / 100) ** weeks
        status = "reached" if latest <= plan.target_kg else "faster" if latest < low else "slower" if latest > high else "on_track"
    eta = None
    if plan and latest is not None and rate and rate < 0 and latest > plan.target_kg:
        eta = iso(latest_day + timedelta(days=round((latest - plan.target_kg) / -rate * 7)))
    monthly: Dict[str, List[float]] = {}
    for d, v in raw.items():
        monthly.setdefault(d.strftime("%Y-%m"), []).append(v)
    waist = [{"date": iso(r["date"]), "value": r["waist_cm"]} for r in rows if r.get("waist_cm") is not None][-16:]
    return {
        "page": "body", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
        "plan": {"start_date": iso(plan.start_date), "start_kg": plan.start_kg, "target_kg": plan.target_kg,
                 "weekly_loss_pct": plan.weekly_loss_pct} if plan else None,
        "latest": {"date": iso(latest_day), "avg7": latest, "rate_per_week": rate,
                   "rate_pct": (rate / latest * 100) if rate is not None and latest else None,
                   "to_go": (latest - plan.target_kg) if plan and latest is not None else None,
                   "since_start": (latest - plan.start_kg) if plan and latest is not None else None,
                   "status": status, "eta": eta, "last_weighed": iso(max(raw)) if raw else None},
        "points": [{"date": iso(d), "kg": raw[d]} for d in sorted(raw) if d >= start],
        "avg7": [{"date": iso(d), "kg": smooth[d]} for d in sorted(smooth) if d >= start],
        "corridor": corridor,
        "monthly": [{"month": m, "kg": statistics.median(v), "n": len(v)} for m, v in sorted(monthly.items())],
        "waist": waist, "dropped": dropped,
        "weighed_days_14": sum(1 for k in range(14) if end - timedelta(days=k) in raw),
    }
