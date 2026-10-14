"""Body & mind load (#load, under Schedule): what is being asked of you, week by week, from the body and from the
mind: the 8 weeks behind you, this week and the 4 ahead.

- Training (the body): the Recovery page's training load, effort x minutes, summed per week. Weeks ahead (and the
  rest of this week) hold the sessions planned in [plan.training], each at the median load of your sessions in the
  last 28 days, kept apart as planned.
- Calendar (the mind's hours): hours of classes and work in events.csv per week; weeks ahead from the calendar as it
  stands.
- Deadlines (the mind's pressure): the share of grade due that week (deadlines.csv weight_pct, ungraded ones count
  as 0) and how many are due.
Each is set against your normal: the middle half of the 8 full weeks before this one, from at least 4 weeks with the
record; above that band reads as heavier than usual. A past week (or this one, done plus planned) where training was
heavier than usual while the calendar or the deadlines were too had body and mind loaded together ("stacked"). A
week ahead is not judged on training, since a plan is not a load (not every planned session happens); it is flagged
instead when the mind's side is heavier than usual and the plan still holds your usual number of sessions or more:
the week to plan lighter. The heaviest week ahead is named. Nothing is added into one number: training load and grade
share are not the same kind of thing.
"""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ..context import Context, iso
from . import plans
from . import recovery as recovery_page
from .week import monday

PAST_WEEKS = 8
AHEAD_WEEKS = 4
MIN_WEEKS = 4
MEASURES = ("training", "calendar", "deadlines")
BUSY_KINDS = ("class", "work")


def _band(values: List[float]) -> Optional[Dict[str, float]]:
    if len(values) < MIN_WEEKS:
        return None
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"q1": q1, "median": median, "q3": q3, "weeks": len(values)}


def _state(value: Optional[float], band: Optional[Dict[str, float]]) -> Optional[str]:
    if value is None or band is None:
        return None
    return "high" if value > band["q3"] else "low" if value < band["q1"] else "normal"


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    today = min(date.fromisoformat(day) if day else ctx.today, ctx.today)
    this = monday(today)
    starts = [this + timedelta(days=7 * k) for k in range(-PAST_WEEKS, AHEAD_WEEKS + 1)]
    days = recovery_page.daily_load(ctx, today)
    recent = [v["load"] for d, v in days.items() if v["load"] > 0 and today - timedelta(days=28) < d <= today]
    session = statistics.median(recent) if recent else None
    events = [e for e in ctx.store.rows("events") if e["kind"] in BUSY_KINDS and e["end"] > e["start"]]
    has_calendar = ctx.store.load("events").present
    deadlines = ctx.store.rows("deadlines")
    has_deadlines = ctx.store.load("deadlines").present
    weeks = []
    for ws in starts:
        we = ws + timedelta(days=7)
        span = [ws + timedelta(days=k) for k in range(7)]
        known = [d for d in span if d in days and d <= today]
        planned = [d for d in span if d > today and plans.training_for(ctx.cfg, d)]
        training = sum(days[d]["load"] for d in known) if known else None
        sessions = sum(1 for d in known if days[d]["load"] > 0)
        due = [x for x in deadlines if ws <= x["due"].date() < we]
        weeks.append({
            "start": iso(ws), "when": "past" if ws < this else "now" if ws == this else "ahead",
            "training": training,
            "planned": len(planned) * session if planned and session else None, "planned_sessions": len(planned),
            "sessions": sessions,
            "calendar": sum((e["end"] - e["start"]).total_seconds() / 3600 for e in events if ws <= e["start"].date() < we)
            if has_calendar else None,
            "deadlines": sum(x.get("weight_pct") or 0 for x in due) if has_deadlines else None,
            "deadline_count": len(due),
            "due": [{"due": iso(x["due"]), "title": x["title"], "group": x.get("group"), "weight_pct": x.get("weight_pct"),
                     "status": x.get("status") or "todo"} for x in sorted(due, key=lambda x: x["due"])],
        })
    past = [w for w in weeks if w["when"] == "past"]
    bands = {k: _band([w[k] for w in past if w[k] is not None]) for k in MEASURES}
    counts = [w["sessions"] for w in past if w["training"] is not None]
    usual_sessions = statistics.median(counts) if len(counts) >= MIN_WEEKS else None
    for w in weeks:
        # this week: what is done so far plus what is still planned; a week ahead: not judged on training at all
        training = w["training"] if w["when"] == "past" else (
            (w["training"] or 0) + (w["planned"] or 0) if w["when"] == "now" and (w["training"] is not None or w["planned"]) else None)
        w["state"] = {"training": _state(training, bands["training"]),
                      "calendar": _state(w["calendar"], bands["calendar"]), "deadlines": _state(w["deadlines"], bands["deadlines"])}
        mind = "high" in (w["state"]["calendar"], w["state"]["deadlines"])
        w["mind_heavy"] = mind
        w["stacked"] = mind and w["state"]["training"] == "high"
        w["plan_lighter"] = (w["when"] == "ahead" and mind and usual_sessions is not None
                             and w["planned_sessions"] > 0 and w["planned_sessions"] >= usual_sessions)
    now = next(w for w in weeks if w["when"] == "now")
    ahead = [w for w in weeks if w["when"] in ("now", "ahead")]
    heaviest = max(ahead, key=lambda w: ((w["deadlines"] or 0), (w["calendar"] or 0))) if ahead else None
    if heaviest is not None and not (heaviest["deadlines"] or heaviest["calendar"]):
        heaviest = None
    return {"page": "load", "day": iso(today), "today": iso(ctx.today), "now": iso(ctx.now),
            "weeks": weeks, "bands": bands, "this_week": now,
            "heaviest": {"start": heaviest["start"], "deadlines": heaviest["deadlines"], "calendar": heaviest["calendar"],
                         "count": heaviest["deadline_count"]} if heaviest else None,
            "session_load": session, "usual_sessions": usual_sessions,
            "training": recovery_page.load_summary(days, today),
            "training_days": [{"date": iso(d), **({"load": days[d]["load"], "minutes": days[d]["minutes"],
                                                   "rated_min": days[d]["rated_min"], "sessions": days[d]["sessions"]}
                                                  if d in days else {"load": None})}
                              for d in (today - timedelta(days=k) for k in range(recovery_page.CHART_DAYS - 1, -1, -1))],
            "rule": {"past_weeks": PAST_WEEKS, "ahead_weeks": AHEAD_WEEKS, "min_weeks": MIN_WEEKS,
                     "acute": recovery_page.ACUTE, "chronic": recovery_page.CHRONIC, "min_rated": recovery_page.MIN_RATED_SHARE}}
