"""What to adjust today: at most three things, at most one each for training, sleep, food and daytime screens, each
with the reason the numbers give and a link to the page that shows them.

This is what makes the app proactive: instead of waiting for you to read every page, it reads them for you each
morning and names what is off and what to do about it today. The rules are fixed and printed here; there is no
model and no score. They are habits, not medical advice.

Candidates, highest priority first within each kind (a kind gets at most one):
- training
  - ease: recovery is below your normal (the Today page's verdict) and training is planned or the week still needs
    minutes. Swap the session for something easy.
  - deload: the last 7 days of workouts are well above the 4 weeks before (the Exercise page's load over 1.3) and
    recovery is not better than usual.
  - move: the week's active-minute goal is not met yet and at least 10 minutes of today's share of what is left are
    still to do; recovery not low.
  - strength: strength days are short of the goal and the days left barely fit them; recovery not low.
  (move and strength need activity records in the last 7 days: without them there is no telling what is left.)
- sleep
  - asleep_by: recovery is below normal, or last night was more than 30 minutes short of the target. Go to sleep by
    tonight's time (Sleep page: the alarm minus the target hours).
  - phone_away: screens in the hour before sleep are worse than your normal (Drain page) or last night had more than
    15 minutes of entertainment in that hour. Put the phone away at tonight's time.
- food (logged days of the last 7, at least 3)
  - late_meal: on 2 or more of them the last meal started less than plan.food.last_meal_gap_h before sleep.
  - protein: protein averaged under 90% of the target.
  - kcal: energy averaged above plan.food.kcal_max.
- screens (the daytime; the hour before sleep is the sleep item's), whole screen days of the last 7, at least 3
  - fun_cap: entertainment & social over the last 7 days averaged above plan.screen.entertainment_max_hours, or, with
    no plan, above your normal (both as the Drain page judges them). Keep it under the plan today, or under the
    median of the 28 days before (rounded to half hours) when there is no plan.
When more than three kinds have something, the first three in the order training, sleep, food, screens are kept
(screens come last: the screen habit that touches recovery most, the hour before sleep, is the sleep item's).
Nothing off means a steady day: the page says so instead of inventing advice.

The Follow-up page (modules/followup.py) checks each of these against what the data shows the day after.
"""
import math
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from ..context import FUN, Context, iso
from . import exercise as exercise_page
from . import food as food_page
from . import plans

MAX_ITEMS = 3
WINDOW = 7
MIN_LOGGED = 3
PROTEIN_SHORT = 0.9
SHORT_NIGHT_MIN = 30
CALM_LAST_HOUR_MIN = 15
MIN_MOVE = 10  # minutes: less than this left for today is not worth a line
BASELINE = 28  # days of screens before the window that make "your normal" for the fun cap without a plan
DOMAINS = ("training", "sleep", "food", "screen")
# every piece of advice, in the order the pages list them
KEYS = ("ease", "deload", "move", "strength", "asleep_by", "phone_away", "late_meal", "protein", "kcal", "fun_cap")


def build(ctx: Context, day: date, recovery: Dict[str, Any], drain: Dict[str, Any]) -> Dict[str, Any]:
    """``recovery`` and ``drain`` are the Today page's own (so both cards always agree)."""
    items: List[Dict[str, Any]] = []
    low = recovery["verdict"] == "low"
    worse = [m["key"] for m in recovery["metrics"] if m["tone"] == "bad"]

    # ---- training
    week = exercise_page.week_status(ctx, day)
    planned = plans.training_for(ctx.cfg, day)
    # without activity records in the last 7 days there is no telling what the week still needs
    minutes = exercise_page.active_minutes(ctx, day)
    tracked = any(day - timedelta(days=k) in minutes for k in range(1, WINDOW + 1))
    load = exercise_page.build(ctx, iso(day))["load"]
    if low and (planned or week["remaining_min"] > 0):
        items.append({"key": "ease", "domain": "training", "params": {"planned": planned}, "why": {"worse": worse},
                      "link": "#exercise"})
    elif load["state"] == "high" and recovery["verdict"] != "good":
        items.append({"key": "deload", "domain": "training", "params": {"ratio": load["ratio"]},
                      "why": {"acute": load["acute_min"], "chronic": load["chronic_min"]}, "link": "#exercise"})
    elif tracked and not low and week["is_current"] and week["remaining_min"] > 0 and week["need_today_min"] - week["today_min"] >= MIN_MOVE:
        items.append({"key": "move", "domain": "training",
                      "params": {"min": math.ceil(week["need_today_min"] - week["today_min"])},
                      "why": {"remaining": week["remaining_min"], "days_left": week["days_left"],
                              "goal": exercise_page.goal(ctx.cfg)["weekly_min"]}, "link": "#exercise"})
    elif tracked and not low and week["is_current"] and 0 < week["strength_left"] and week["days_left"] <= week["strength_left"] + 1:
        items.append({"key": "strength", "domain": "training", "params": {"left": week["strength_left"]},
                      "why": {"days_left": week["days_left"]}, "link": "#exercise"})

    # ---- sleep
    tonight = plans.tonight(ctx, day)
    body = ctx.store.by_date("body_daily")
    last_night = (body.get(day) or {}).get("sleep_min")
    target = (ctx.cfg.sleep.target_hours or 8) * 60
    short = last_night is not None and last_night < target - SHORT_NIGHT_MIN
    fun_last = ctx.fun_before_sleep(day - timedelta(days=1))
    screens_bad = "before_sleep" in (drain.get("worse") or []) or (fun_last is not None and fun_last > CALM_LAST_HOUR_MIN)
    if tonight and (low or short):
        items.append({"key": "asleep_by", "domain": "sleep", "params": {"clock": tonight["asleep_by"], "alarm": tonight["alarm"]},
                      "why": {"low": low, "short_by": (target - last_night) if short else None}, "link": "#sleep"})
    elif tonight and screens_bad:
        items.append({"key": "phone_away", "domain": "sleep", "params": {"clock": tonight["phone_away"]},
                      "why": {"drain": "before_sleep" in (drain.get("worse") or []), "last_night": fun_last}, "link": "#sleep"})

    # ---- food
    days = food_page.food_days(ctx, day)
    window = [day - timedelta(days=k) for k in range(1, WINDOW + 1)]
    logged = [days[d] for d in window if d in days and days[d]["full"]]
    plan = ctx.cfg.food
    if len(logged) >= MIN_LOGGED:
        late = [x for x in logged if x["late"]]
        known_gap = [x for x in logged if x["late"] is not None]
        protein = food_page.protein_target(ctx, day)["grams"]
        got = [x["protein_g"] for x in logged if x["protein_g"] is not None]
        avg_protein = sum(got) / len(got) if got else None
        kcal = [x["kcal"] for x in logged if x["kcal"] is not None]
        avg_kcal = sum(kcal) / len(kcal) if kcal else None
        if len(late) >= 2:
            dinner_by = None
            if tonight:
                dinner_by = iso(datetime.fromisoformat(tonight["asleep_by"]) - timedelta(hours=plan.last_meal_gap_h))
            items.append({"key": "late_meal", "domain": "food", "params": {"clock": dinner_by, "hours": plan.last_meal_gap_h},
                          "why": {"late": len(late), "known": len(known_gap)}, "link": "#food"})
        elif protein and avg_protein is not None and avg_protein < PROTEIN_SHORT * protein:
            items.append({"key": "protein", "domain": "food", "params": {"more_g": protein - avg_protein, "target_g": protein},
                          "why": {"avg_g": avg_protein, "days": len(got)}, "link": "#food"})
        elif plan.kcal_max is not None and avg_kcal is not None and avg_kcal > plan.kcal_max:
            items.append({"key": "kcal", "domain": "food", "params": {"max": plan.kcal_max},
                          "why": {"avg": avg_kcal, "days": len(kcal)}, "link": "#food"})

    # ---- screens (daytime)
    screen = ctx.screen_known_days()
    seen = [screen[d].share(FUN) for d in window if d in screen]
    limit_h = ctx.cfg.screen.entertainment_max_hours
    over_plan = any(x["key"] == "fun" for x in drain.get("plan_off") or [])  # the Today page's drain card
    over_normal = "fun" in (drain.get("worse") or [])
    if len(seen) >= MIN_LOGGED and (over_plan or (limit_h is None and over_normal)):
        if limit_h is not None:
            cap_h, source = limit_h, "plan"
        else:
            base = [screen[d].share(FUN) for d in (day - timedelta(days=WINDOW + 1 + k) for k in range(BASELINE)) if d in screen]
            cap_h, source = (max(0.5, round(statistics.median(base) / 30) / 2), "normal") if base else (None, "normal")
        if cap_h is not None:
            items.append({"key": "fun_cap", "domain": "screen", "params": {"hours": cap_h, "source": source},
                          "why": {"avg": sum(seen) / len(seen), "days": len(seen)}, "link": "#time"})

    order = {d: i for i, d in enumerate(DOMAINS)}
    items.sort(key=lambda x: order[x["domain"]])
    return {"items": items[:MAX_ITEMS], "steady": not items,
            "inputs": {"recovery": recovery["verdict"], "week_remaining": week["remaining_min"],
                       "logged_days": len(logged), "tonight": bool(tonight)}}
