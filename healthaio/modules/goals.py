"""Goals: every plan in healthaio.toml in one place, and on how many days each one was kept.

Rules
- A daily goal is met, missed or unknown on each of the last 28 days (four weeks of dots). The count is "kept on n
  of the k days with a record": never a streak, never a score, and a day without a record is not a missed day.
- Sleep goals use the same checks as the Sleep page, for the night that ended that morning; a calm last hour means
  no more than 15 minutes of entertainment & social in the hour before falling asleep (a rule of the app, there is
  no plan for it). Food goals count logged days only (see the Food page). Screen goals count whole days.
- Weekly goals (active minutes, strength days): the last four calendar weeks, plus this week so far.
- Weight: the Body page's place against the planned corridor (listed with food, the plan it mostly answers to).
- A plan that is not set is listed too, so this page is also the menu of what can be planned.
- Each goal names the healthaio.toml fields that set it ("edit"), so the page can change them: a change is a line in
  goals.jsonl laid over the file (see goal_log), marked "set_here". Proposals an assistant wrote wait in
  "proposals" until you accept or decline them; until then they change nothing. The built-in rule (a calm last
  hour) and the alarm ladder's goals are not edited here.
- The top line names the goal kept most often over the last 7 days and the one kept least often (each needs at
  least 3 days with a record), or says they are all kept alike.
"""
from datetime import date, time, timedelta
from typing import Any, Callable, Dict, List, Optional

from .. import goal_log
from ..config import Config
from ..context import FOCUS, FUN, Context, iso
from . import body as body_page
from . import exercise as exercise_page
from . import food as food_page
from . import plans
from .sleep import night_checks
from .week import monday

DAYS = 28
RECENT = 7
MIN_KNOWN = 3
WEEKS = 4


def _daily(key: str, domain: str, source: str, target: Dict[str, Any], test: Callable[[date], Optional[bool]],
           end: date, link: str) -> Dict[str, Any]:
    days = [{"date": iso(end - timedelta(days=k)), "met": test(end - timedelta(days=k))} for k in range(DAYS - 1, -1, -1)]
    recent = days[-RECENT:]
    return {"key": key, "domain": domain, "kind": "daily", "source": source, "target": target, "days": days,
            "kept": sum(1 for x in recent if x["met"]), "known": sum(1 for x in recent if x["met"] is not None),
            "kept28": sum(1 for x in days if x["met"]), "known28": sum(1 for x in days if x["met"] is not None),
            "link": link}


def _unset(key: str, domain: str, section: str, link: str) -> Dict[str, Any]:
    return {"key": key, "domain": domain, "kind": "unset", "source": "unset", "section": section, "link": link}


def _fields(r: Dict[str, Any], cfg: Config) -> List[str]:
    """The healthaio.toml fields a goal row is set by, when the page may change them."""
    if r["key"] in ("asleep_in_time", "woke_on_time") and cfg.wake_shift:
        return []  # the alarm ladder moves these; it is set in the file
    return {"asleep_in_time": ["sleep.bedtime"], "woke_on_time": ["sleep.wake"], "slept_enough": ["sleep.target_hours"],
            "weekly_min": ["exercise.weekly_min"], "strength_days": ["exercise.strength_days"],
            "kcal_range": ["food.kcal_min", "food.kcal_max"], "protein": ["food.protein_g_per_kg"],
            "last_meal": ["food.last_meal_gap_h"], "weight_pace": ["weight.target_kg"],
            "focus_min": ["screen.work_min_hours"], "fun_max": ["screen.entertainment_max_hours"]}.get(r["key"], [])


def _value(cfg: Config, name: str) -> Any:
    """A field's value as the pages use it now (the guideline for exercise when no plan sets it)."""
    section, key = name.split(".", 1)
    if section == "weight":
        return cfg.weight.target_kg if cfg.weight else None
    if section == "exercise":
        return exercise_page.goal(cfg)[key]
    value = getattr(getattr(cfg, section), key)
    return value.strftime("%H:%M") if isinstance(value, time) else value


def _spec(cfg: Config, name: str, **extra: Any) -> Dict[str, Any]:
    return {"field": name, **goal_log.FIELDS[name], "value": _value(cfg, name), **extra}


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    end = min(date.fromisoformat(day) if day else ctx.today, ctx.today)
    cfg = ctx.cfg
    body = ctx.store.by_date("body_daily")
    ladder = plans.alarms(ctx, end)
    alarm_by_day = {x["date"]: x["alarm"] for x in ladder}
    nights: Dict[date, Dict[str, Any]] = {}

    def night(d: date) -> Dict[str, Any]:
        if d not in nights:
            nights[d] = night_checks(ctx, d, body, alarm_by_day)
        return nights[d]

    rows: List[Dict[str, Any]] = []
    has_sleep_plan = bool(cfg.sleep.bedtime or cfg.wake_shift)
    if has_sleep_plan:
        target = {"clock": cfg.sleep.bedtime.strftime("%H:%M")} if cfg.sleep.bedtime and not cfg.wake_shift else {"before_alarm_h": cfg.sleep.target_hours or 8}
        rows.append(_daily("asleep_in_time", "sleep", "plan", target, lambda d: night(d)["asleep_in_time"], end, "#sleep"))
    else:
        rows.append(_unset("asleep_in_time", "sleep", "plan.sleep", "#sleep"))
    rows.append(_daily("slept_enough", "sleep", "plan" if cfg.sleep.target_hours else "rule",
                       {"hours": cfg.sleep.target_hours or 8}, lambda d: night(d)["slept_enough"], end, "#sleep"))
    if cfg.wake_shift or cfg.sleep.wake:
        target = {"shift": True} if cfg.wake_shift else {"clock": cfg.sleep.wake.strftime("%H:%M")}
        rows.append(_daily("woke_on_time", "sleep", "plan", target, lambda d: night(d)["woke_on_time"], end, "#sleep"))
    rows.append(_daily("calm_last_hour", "sleep", "rule", {"min": 15}, lambda d: night(d)["screen_before_sleep_ok"], end, "#sleep"))

    # exercise: weekly
    g = exercise_page.goal(cfg)
    minutes = exercise_page.active_minutes(ctx, end)
    workouts = [w for w in ctx.store.rows("workouts") if w["start"].date() <= end]
    weeks = []
    for w in range(WEEKS, -1, -1):
        ws = monday(end) - timedelta(days=7 * w)
        span = [ws + timedelta(days=k) for k in range(7) if ws + timedelta(days=k) <= end]
        known = [minutes[d] for d in span if d in minutes]
        strength = len({x["start"].date() for x in workouts if ws <= x["start"].date() < ws + timedelta(days=7)
                        and exercise_page.kind_of(x["type"]) == "strength"})
        whole = len(span) == 7
        weeks.append({"week_start": iso(ws), "partial": not whole, "known_days": len(known),
                      "minutes": sum(known) if known else None, "strength_days": strength})
    for key, field, limit in (("weekly_min", "minutes", g["weekly_min"]), ("strength_days", "strength_days", g["strength_days"])):
        out = [{"week_start": x["week_start"], "value": x[field], "partial": x["partial"],
                "met": None if x[field] is None or (x["partial"] and x[field] < limit) else x[field] >= limit} for x in weeks]
        done = [x for x in out if not x["partial"] and x["met"] is not None]
        rows.append({"key": key, "domain": "exercise", "kind": "weekly", "source": g["source"], "target": {"value": limit},
                     "weeks": out, "kept": sum(1 for x in done if x["met"]), "known": len(done), "link": "#exercise"})

    # food: daily, logged days only
    days = food_page.food_days(ctx, end)
    logged = {d: x for d, x in days.items() if x["full"]}
    food = cfg.food
    if food.kcal_min is not None or food.kcal_max is not None:
        def kcal_ok(d: date) -> Optional[bool]:
            x = logged.get(d)
            if not x or x["kcal"] is None:
                return None
            return (food.kcal_min is None or x["kcal"] >= food.kcal_min) and (food.kcal_max is None or x["kcal"] <= food.kcal_max)
        rows.append(_daily("kcal_range", "food", "plan", {"low": food.kcal_min, "high": food.kcal_max}, kcal_ok, end, "#food"))
    else:
        rows.append(_unset("kcal_range", "food", "plan.food", "#food"))
    protein = food_page.protein_target(ctx, end)
    if protein["grams"]:
        rows.append(_daily("protein", "food", "plan", {"grams": protein["grams"], "per_kg": protein["per_kg"]},
                           lambda d: None if not logged.get(d) or logged[d]["protein_g"] is None else logged[d]["protein_g"] >= protein["grams"],
                           end, "#food"))
    else:
        rows.append(_unset("protein", "food", "plan.food", "#food"))
    rows.append(_daily("last_meal", "food", "plan" if days else "rule", {"hours": food.last_meal_gap_h},
                       lambda d: None if not logged.get(d) or logged[d]["late"] is None else not logged[d]["late"], end, "#food"))

    # weight
    if cfg.weight:
        latest = body_page.build(ctx, iso(end))["latest"]
        rows.append({"key": "weight_pace", "domain": "food", "kind": "status", "source": "plan",
                     "target": {"target_kg": cfg.weight.target_kg, "weekly_loss_pct": cfg.weight.weekly_loss_pct},
                     "status": latest["status"], "value": latest["avg7"], "rate_pct": latest["rate_pct"],
                     "eta": latest["eta"], "link": "#body"})
    else:
        rows.append(_unset("weight_pace", "food", "plan.weight", "#body"))

    # screens: whole days only
    screen = ctx.screen_known_days()
    for key, cats, op, hours in (("focus_min", FOCUS, ">=", cfg.screen.work_min_hours),
                                 ("fun_max", FUN, "<=", cfg.screen.entertainment_max_hours)):
        if hours is None:
            rows.append(_unset(key, "screens", "plan.screen", "#time"))
            continue
        limit = hours * 60

        def test(d: date, cats=cats, op=op, limit=limit) -> Optional[bool]:
            sd = screen.get(d)
            if sd is None:
                return None
            value = sd.share(cats)
            return value >= limit if op == ">=" else value <= limit
        rows.append(_daily(key, "screens", "plan", {"hours": hours}, test, end, "#time"))

    # what the page may change, and which goals were last set here (by you, or an assistant's proposal you accepted)
    for r in rows:
        names = _fields(r, cfg)
        r["edit"] = [_spec(cfg, n) for n in names]
        mine = [cfg.goals_set[n] for n in names if n in cfg.goals_set]
        if mine:
            last = max(mine, key=lambda x: x.get("at") or "")
            r["set_here"] = {"by": last["by"], "at": last["at"], "accepted": last["accepted"]}
    proposals = [{"id": e["id"], "at": e.get("at"), "by": e.get("by"), "note": e.get("note"),
                  "changes": [_spec(cfg, n, to=v) for n, v in e["changes"].items() if n in goal_log.FIELDS]}
                 for e in cfg.goals_proposed]

    # the top line: kept most and least often over the last 7 days (daily goals with enough records)
    ranked = [r for r in rows if r["kind"] == "daily" and r["known"] >= MIN_KNOWN]
    ranked.sort(key=lambda r: (r["kept"] / r["known"], r["known"]))
    best = ranked[-1] if ranked else None
    worst = ranked[0] if ranked else None
    same = bool(ranked) and best["kept"] / best["known"] == worst["kept"] / worst["known"]
    return {"page": "goals", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
            "rows": rows, "domains": ["sleep", "exercise", "food", "screens"], "proposals": proposals,
            "best": None if same or not best else {"key": best["key"], "kept": best["kept"], "known": best["known"]},
            "worst": None if same or not worst else {"key": worst["key"], "kept": worst["kept"], "known": worst["known"]},
            "same": same, "set": sum(1 for r in rows if r["kind"] != "unset"), "unset": sum(1 for r in rows if r["kind"] == "unset"),
            "rule": {"days": DAYS, "recent": RECENT, "min_known": MIN_KNOWN, "weeks": WEEKS}}
