"""Plan arithmetic shared by several pages: today's training, screen targets, and the wake-time shift."""
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from ..config import WEEKDAYS, Config
from ..context import Context, iso

PHONE_AWAY_MIN = 30


def training_for(cfg: Config, day: date) -> Optional[str]:
    return cfg.training.get(WEEKDAYS[day.weekday()])


def screen_targets(cfg: Config, series: Dict[str, Dict[date, float]], last: date) -> List[Dict[str, Any]]:
    out = []
    plan = cfg.screen
    checks = [("focus", ">=", plan.work_min_hours), ("fun", "<=", plan.entertainment_max_hours)]
    for key, op, hours in checks:
        if hours is None:
            continue
        limit = hours * 60
        days = [last - timedelta(days=k) for k in range(7)]
        values = series.get(key, {})
        met = [d for d in days if d in values and (values[d] >= limit if op == ">=" else values[d] <= limit)]
        known = [d for d in days if d in values]
        value = values.get(last)
        out.append({"key": key, "op": op, "limit_min": limit, "value": value,
                    "met": None if value is None else (value >= limit if op == ">=" else value <= limit),
                    "week_met": len(met), "week_known": len(known)})
    return out


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def alarms(ctx: Context, until: date) -> List[Dict[str, Any]]:
    """Day by day from the shift start: that morning's alarm, when you woke, whether it counted as on time.

    The alarm moves one step earlier after an on-time morning and stays put otherwise (late or no record).
    Nothing is stored: a late-arriving wake time simply recomputes the ladder.
    """
    shift = ctx.cfg.wake_shift
    if shift is None or until < shift.start:
        return []
    body = ctx.store.by_date("body_daily")
    alarm = _minutes(shift.first_alarm)
    floor = _minutes(shift.final_alarm)
    out = []
    d = shift.start
    while d <= until:
        row = body.get(d) or {}
        woke = row.get("sleep_end")
        woke_min = woke.hour * 60 + woke.minute if woke else None
        on_time = None if woke_min is None else woke_min <= alarm + shift.grace_min
        out.append({"date": iso(d), "alarm": f"{alarm // 60:02d}:{alarm % 60:02d}",
                    "woke": iso(woke), "on_time": on_time, "asleep": iso(row.get("sleep_start")),
                    "sleep_min": row.get("sleep_min")})
        if on_time:
            alarm = max(floor, alarm - int(shift.step_min))
        d += timedelta(days=1)
    return out


def next_alarm(ctx: Context, ladder: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    shift = ctx.cfg.wake_shift
    if shift is None or not ladder:
        return None
    last = ladder[-1]
    alarm_today = last["alarm"]
    hh, mm = map(int, alarm_today.split(":"))
    alarm_dt = datetime.combine(date.fromisoformat(last["date"]), time(hh, mm))
    if last["date"] == iso(ctx.today) and last["woke"] is None and ctx.now < alarm_dt:
        return {"date": last["date"], "alarm": alarm_today}
    # tomorrow's alarm follows today's result
    floor = _minutes(shift.final_alarm)
    minutes = hh * 60 + mm
    if last["on_time"]:
        minutes = max(floor, minutes - int(shift.step_min))
    nxt = date.fromisoformat(last["date"]) + timedelta(days=1)
    return {"date": iso(nxt), "alarm": f"{minutes // 60:02d}:{minutes % 60:02d}"}


def tonight(ctx: Context, day: date) -> Optional[Dict[str, Any]]:
    """Tonight's targets: when to put the phone away, when to be asleep, when the alarm rings."""
    target = ctx.cfg.sleep.target_hours or 8
    if ctx.cfg.wake_shift is not None:
        ladder = alarms(ctx, day)
        nxt = next_alarm(ctx, ladder) if ladder else None
        if nxt:
            hh, mm = map(int, nxt["alarm"].split(":"))
            wake = datetime.combine(date.fromisoformat(nxt["date"]), time(hh, mm))
            asleep = wake - timedelta(hours=target)
            return {"source": "wake_shift", "alarm": iso(wake), "asleep_by": iso(asleep),
                    "phone_away": iso(asleep - timedelta(minutes=PHONE_AWAY_MIN)),
                    "last": ladder[-1] if ladder else None}
    plan = ctx.cfg.sleep
    if plan.wake:
        wake = datetime.combine(day + timedelta(days=1), plan.wake)
        asleep = datetime.combine(day, plan.bedtime) if plan.bedtime else wake - timedelta(hours=target)
        if plan.bedtime and plan.bedtime < time(12):
            asleep += timedelta(days=1)
        return {"source": "sleep_plan", "alarm": iso(wake), "asleep_by": iso(asleep),
                "phone_away": iso(asleep - timedelta(minutes=PHONE_AWAY_MIN)), "last": None}
    return None
