"""Sleep: three weeks of nights, the wake-time ladder, and a week of simple checks."""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import Context, iso
from . import plans

NIGHTS = 21
FUN_BEFORE_SLEEP_OK_MIN = 15


def _avg_clock(values: List[float]) -> Optional[str]:
    return stats.clock_from_noon(statistics.fmean(values)) if values else None


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    end = date.fromisoformat(day) if day else ctx.today
    body = ctx.store.by_date("body_daily")
    cfg = ctx.cfg
    ladder = plans.alarms(ctx, end)
    alarm_by_day = {x["date"]: x["alarm"] for x in ladder}
    nights = []
    for k in range(NIGHTS - 1, -1, -1):
        d = end - timedelta(days=k)
        row = body.get(d) or {}
        nights.append({"date": iso(d), "start": iso(row.get("sleep_start")), "end": iso(row.get("sleep_end")),
                       "sleep_min": row.get("sleep_min"), "in_bed_min": row.get("in_bed_min"),
                       "alarm": alarm_by_day.get(iso(d))})

    def window(offset: int) -> Dict[str, Any]:
        days = [end - timedelta(days=offset + k) for k in range(7)]
        rows = [body[d] for d in days if d in body and body[d].get("sleep_start")]
        onset = [stats.minutes_since_noon(r["sleep_start"]) for r in rows]
        wake = [stats.minutes_of_day(r["sleep_end"]) for r in rows]
        dur = [r["sleep_min"] for r in rows if r.get("sleep_min") is not None]
        return {"nights": len(rows), "onset": _avg_clock(onset),
                "wake": stats.clock_from_midnight(statistics.fmean(wake)) if wake else None,
                "onset_min": statistics.fmean(onset) if onset else None,
                "wake_min": statistics.fmean(wake) if wake else None,
                "sleep_min": statistics.fmean(dur) if dur else None,
                "onset_spread_min": statistics.pstdev(onset) if len(onset) >= 3 else None}

    checks = [night_checks(ctx, end - timedelta(days=k), body, alarm_by_day) for k in range(6, -1, -1)]
    shift = cfg.wake_shift
    return {
        "page": "sleep", "day": iso(end), "today": iso(ctx.today), "now": iso(ctx.now),
        "plan": {"target_hours": cfg.sleep.target_hours, "bedtime": cfg.sleep.bedtime.strftime("%H:%M") if cfg.sleep.bedtime else None,
                 "wake": cfg.sleep.wake.strftime("%H:%M") if cfg.sleep.wake else None},
        "shift": {"start": iso(shift.start), "first_alarm": shift.first_alarm.strftime("%H:%M"),
                  "final_alarm": shift.final_alarm.strftime("%H:%M"), "step_min": shift.step_min,
                  "grace_min": shift.grace_min, "ladder": ladder,
                  "moved_min": (stats.minutes_since_noon(shift.first_alarm)
                                - stats.minutes_since_noon(_parse(ladder[-1]["alarm"]))) if ladder else 0} if shift else None,
        "tonight": plans.tonight(ctx, end),
        "nights": nights, "this_week": window(0), "last_week": window(7), "checks": checks,
        "rules": {"fun_before_sleep_ok_min": FUN_BEFORE_SLEEP_OK_MIN, "slack_min": 30},
    }


def night_checks(ctx: Context, d: date, body: Dict[date, Dict[str, Any]], alarm_by_day: Dict[str, str]) -> Dict[str, Any]:
    """The night that ended on ``d``: up with the alarm, asleep in time, slept enough, a calm last hour (None = no record
    or no plan to check against). The Goals page counts the same checks over four weeks."""
    cfg = ctx.cfg
    target_min = (cfg.sleep.target_hours or 8) * 60
    row = body.get(d) or {}
    start = row.get("sleep_start")
    alarm = alarm_by_day.get(iso(d))
    woke = row.get("sleep_end")
    on_time = None
    if woke and alarm:
        hh, mm = map(int, alarm.split(":"))
        on_time = woke.hour * 60 + woke.minute <= hh * 60 + mm + (cfg.wake_shift.grace_min if cfg.wake_shift else 15)
    elif woke and cfg.sleep.wake:
        on_time = woke.hour * 60 + woke.minute <= cfg.sleep.wake.hour * 60 + cfg.sleep.wake.minute + 15
    asleep_ok = None
    if start and alarm:  # asleep early enough to get the target hours before the alarm
        asleep_ok = stats.minutes_since_noon(start) <= stats.minutes_since_noon(_parse(alarm)) - target_min
    elif start and cfg.sleep.bedtime:
        asleep_ok = stats.minutes_since_noon(start) <= stats.minutes_since_noon(cfg.sleep.bedtime)
    fun = ctx.fun_before_sleep(d - timedelta(days=1))
    return {"date": iso(d), "woke_on_time": on_time, "asleep_in_time": asleep_ok,
            "slept_enough": None if row.get("sleep_min") is None else row["sleep_min"] >= target_min - 30,
            "screen_before_sleep_ok": None if fun is None else fun <= FUN_BEFORE_SLEEP_OK_MIN,
            "fun_before_sleep_min": fun}


def _parse(text: str):
    from datetime import time
    hh, mm = map(int, text.split(":"))
    return time(hh, mm)
