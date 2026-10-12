"""What every page module receives: settings, the loaded tables, and the current time."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .config import Config
from .store import Store

FOCUS = ("work", "learning")
FUN = ("entertainment", "social")
STRETCH_GAP_MIN = 3  # a quick message inside a work block does not end the stretch


@dataclass
class ScreenDay:
    day: date
    by_category: Dict[str, float] = field(default_factory=dict)
    by_hour: List[Dict[str, float]] = field(default_factory=lambda: [dict() for _ in range(24)])
    by_app: Dict[tuple, float] = field(default_factory=dict)  # (app, device, category) -> minutes
    longest_focus: float = 0.0
    minutes: Dict[int, str] = field(default_factory=dict)  # minute of day -> category (see _minutes for the key)

    @property
    def total(self) -> float:
        return sum(self.by_category.values())

    def share(self, cats) -> float:
        return sum(self.by_category.get(c, 0.0) for c in cats)


ACTIVITIES = ("sleep", "exercise", "calendar", "screen")  # the Time page's lanes, in display order
SCREEN_PARTS = ("focus", "fun", "communication", "other")
CALENDAR_KINDS = ("class", "work", "personal", "other")  # planned training is not counted; workouts are


@dataclass
class TimeDay:
    """One calendar day, minute by minute. Each activity uses its own record, so lanes may overlap.

    ``minutes`` and ``total()`` are what the records say. ``known`` says whether that day has the
    record an activity needs (a night with the watch off, Screen Time not imported yet, the day an
    Apple Health export was made); ``value()`` and ``totals()`` give None for an unknown activity,
    so a missing record is never read as zero.
    """
    day: date
    minutes: Dict[str, set] = field(default_factory=lambda: {a: set() for a in ACTIVITIES})
    screen_parts: Dict[str, float] = field(default_factory=dict)
    by_hour: List[Dict[str, float]] = field(default_factory=lambda: [dict() for _ in range(24)])
    untimed_exercise: float = 0.0  # workout minutes known only as a daily total (no start time)
    has_screen: bool = False
    has_body: bool = False         # body_daily has a row dated this day
    known: Dict[str, bool] = field(default_factory=lambda: {a: False for a in ACTIVITIES})
    length: int = 1440             # real minutes in this day: 1380 or 1500 when the clocks change

    def total(self, activity: str) -> float:
        """Minutes the records hold for ``activity``, whether or not the day's record is complete."""
        extra = self.untimed_exercise if activity == "exercise" else 0.0
        return float(len(self.minutes[activity])) + extra

    def value(self, activity: str) -> Optional[float]:
        return self.total(activity) if self.known[activity] else None

    @property
    def recorded(self) -> float:
        union = set()
        for a in ACTIVITIES:
            union |= self.minutes[a]
        return float(len(union)) + self.untimed_exercise

    @property
    def unrecorded(self) -> float:
        return max(0.0, float(self.length) - self.recorded)

    @property
    def admitted(self) -> bool:
        """Shown as a day of its own: it has a screen record or a body row dated that day. A day that
        only holds the evening part of the next morning's sleep is not."""
        return self.has_screen or self.has_body

    def totals(self) -> Dict[str, Optional[float]]:
        out: Dict[str, Optional[float]] = {a: self.value(a) for a in ACTIVITIES}
        out.update({k: (self.screen_parts.get(k, 0.0) if self.known["screen"] else None) for k in SCREEN_PARTS})
        # "not recorded" needs the two records that cover most of a day: without the night or the
        # screens, the gap would only measure what is missing
        out["not_recorded"] = self.unrecorded if self.known["sleep"] and self.known["screen"] else None
        return out


def _ambiguous_or_missing(t: datetime, tz) -> Tuple[bool, bool]:
    """(ambiguous, missing): a wall-clock time inside the repeated hour when clocks go back, or
    inside the skipped hour when they go forward."""
    a, b = t.replace(tzinfo=tz, fold=0), t.replace(tzinfo=tz, fold=1)
    if a.utcoffset() == b.utcoffset():
        return False, False
    back = a.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    return back == t, back != t


def _missing(t: datetime, tz) -> bool:
    return t.replace(tzinfo=tz).astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != t


def _minutes(start: datetime, end: datetime, tz) -> Iterator[Tuple[date, int, int]]:
    """Each real minute of [start, end) as (local day, minute key, local hour).

    Times are naive local wall-clock times in ``tz``. On the day clocks go forward the skipped
    minutes never happened and are not counted; on the day they go back, a record that runs
    through the repeated hour counts it twice (the second pass gets key 1440 + minute).
    """
    t = start.replace(second=0, microsecond=0)
    if tz is None:
        while t < end:
            yield t.date(), t.hour * 60 + t.minute, t.hour
            t += timedelta(minutes=1)
        return
    utc0 = t.replace(tzinfo=tz).astimezone(timezone.utc)
    utc1 = end.replace(tzinfo=tz).astimezone(timezone.utc)
    amb0, gap0 = _ambiguous_or_missing(t, tz)
    amb1, gap1 = _ambiguous_or_missing(end, tz)
    plain = utc1 - utc0 == end - t and not (gap0 or gap1 or amb0 or amb1) and end - t < timedelta(days=90)
    if plain:  # no change of clocks inside: wall clock = real time
        while t < end:
            yield t.date(), t.hour * 60 + t.minute, t.hour
            t += timedelta(minutes=1)
    elif utc1 - utc0 > end - t and not (gap0 or gap1 or amb0 or amb1):
        u = utc0  # the clocks went back inside: walk real minutes so the repeated hour counts twice
        while u < utc1:
            local = u.astimezone(tz)
            yield local.date(), local.hour * 60 + local.minute + (1440 if local.fold else 0), local.hour
            u += timedelta(minutes=1)
    else:  # the clocks went forward inside (or an end sits in a changeover hour): skip minutes that never happened
        while t < end:
            if not _missing(t, tz):
                yield t.date(), t.hour * 60 + t.minute, t.hour
            t += timedelta(minutes=1)


class Context:
    def __init__(self, cfg: Config, now: Optional[datetime] = None):
        self.cfg = cfg
        self.store = Store(cfg.data_dir)
        try:
            self.tz = cfg.tz
        except Exception:  # no zoneinfo or no tz database: count wall-clock minutes as they are
            self.tz = None
        self.now = now or datetime.now(self.tz).replace(tzinfo=None)
        self._screen: Optional[Dict[date, ScreenDay]] = None
        self._time: Optional[Dict[date, TimeDay]] = None
        self._lengths: Dict[date, int] = {}

    @property
    def today(self) -> date:
        return self.now.date()

    def day_length(self, day: date) -> int:
        """Real minutes from this local midnight to the next: 1440, or 1380 / 1500 when clocks change."""
        if day not in self._lengths:
            if self.tz is None:
                self._lengths[day] = 1440
            else:
                a = datetime.combine(day, time(0)).replace(tzinfo=self.tz).astimezone(timezone.utc)
                b = datetime.combine(day + timedelta(days=1), time(0)).replace(tzinfo=self.tz).astimezone(timezone.utc)
                self._lengths[day] = int(round((b - a).total_seconds() / 60))
        return self._lengths[day]

    # ---- screen time, counted once across devices -------------------------------------------
    def screen_days(self) -> Dict[date, ScreenDay]:
        if self._screen is not None:
            return self._screen
        rank = {name: i for i, name in enumerate(self.cfg.devices)}
        claimed: Dict[date, Dict[int, tuple]] = {}
        for row in self.store.rows("screen_sessions"):
            start, end = row["start"], row["end"]
            if end <= start:
                continue
            priority = rank.get(row["device"], len(rank))
            for day, minute, hour in _minutes(start, end, self.tz):
                day_map = claimed.setdefault(day, {})
                held = day_map.get(minute)
                if held is None or priority < held[0]:
                    day_map[minute] = (priority, row["category"], row["app"], row["device"], hour)
        out: Dict[date, ScreenDay] = {}
        for day, minutes in claimed.items():
            sd = ScreenDay(day=day)
            for minute, (_, cat, app, device, hour) in minutes.items():
                sd.by_category[cat] = sd.by_category.get(cat, 0.0) + 1
                slot = sd.by_hour[hour]
                slot[cat] = slot.get(cat, 0.0) + 1
                sd.by_app[(app, device, cat)] = sd.by_app.get((app, device, cat), 0.0) + 1
                sd.minutes[minute] = cat
            sd.longest_focus = _longest(sd.minutes)
            out[day] = sd
        self._screen = out
        return out

    def time_days(self) -> Dict[date, TimeDay]:
        """Sleep, exercise, calendar and screen minutes for every calendar day that has any of them,
        with what is known for each day (see TimeDay)."""
        if self._time is not None:
            return self._time
        days: Dict[date, TimeDay] = {}

        def get(day: date) -> TimeDay:
            td = days.get(day)
            if td is None:
                td = days[day] = TimeDay(day=day, length=self.day_length(day))
            return td

        def mark(activity: str, start: datetime, end: datetime) -> List[date]:
            touched = []
            for day, minute, hour in _minutes(start, end, self.tz):
                td = get(day)
                if minute not in td.minutes[activity]:
                    td.minutes[activity].add(minute)
                    slot = td.by_hour[hour]
                    slot[activity] = slot.get(activity, 0.0) + 1
                if not touched or touched[-1] != day:
                    touched.append(day)
            return touched

        body = self.store.by_date("body_daily")
        slept = {d for d, row in body.items() if _has_sleep(row)}
        for d, row in body.items():
            get(d).has_body = True
            if d in slept:
                mark("sleep", row["sleep_start"], row["sleep_end"])
        timed: Dict[date, float] = {}
        workout_days = set()
        for w in self.store.rows("workouts"):
            if w["end"] > w["start"]:
                workout_days.update(mark("exercise", w["start"], w["end"]))
                workout_days.add(w["start"].date())
                timed[w["start"].date()] = timed.get(w["start"].date(), 0.0) + (w["end"] - w["start"]).total_seconds() / 60
        for d, row in body.items():  # daily totals without times, only where workouts.csv has nothing
            if row.get("workout_min") and d not in timed:
                get(d).untimed_exercise = float(row["workout_min"])
        for e in self.store.rows("events"):
            if e["kind"] in CALENDAR_KINDS and e["end"] > e["start"]:
                mark("calendar", e["start"], e["end"])
        parts = {"work": "focus", "learning": "focus", "entertainment": "fun", "social": "fun",
                 "communication": "communication", "other": "other"}
        for day, sd in self.screen_days().items():
            td = get(day)
            td.has_screen = True
            for minute, cat in sd.minutes.items():
                td.minutes["screen"].add(minute)
                part = parts.get(cat, "other")
                td.screen_parts[part] = td.screen_parts.get(part, 0.0) + 1
            for hour, cats in enumerate(sd.by_hour):
                slot = td.by_hour[hour]
                for cat, minutes in cats.items():
                    part = parts.get(cat, "other")
                    slot[part] = slot.get(part, 0.0) + minutes

        # what each day's records can tell
        starts = sorted(w["start"].date() for w in self.store.rows("workouts") if w["end"] > w["start"])
        first_w, last_w = (starts[0], starts[-1]) if starts else (None, None)
        has_calendar = self.store.load("events").present
        partial_screen = self.screen_partial_day()
        for d, td in days.items():
            td.known["screen"] = td.has_screen and d != partial_screen
            # the night that ended this morning and the one that ended next morning (its evening part)
            td.known["sleep"] = d in slept and d + timedelta(days=1) in slept
            td.known["calendar"] = has_calendar
            td.known["exercise"] = self._exercise_known(d, body.get(d), d in workout_days, first_w, last_w)
        self._time = days
        return days

    @staticmethod
    def _exercise_known(d: date, row: Optional[Dict[str, Any]], has_workout: bool,
                        first_w: Optional[date], last_w: Optional[date]) -> bool:
        if row is not None and row.get("complete") is False:
            return False  # exported before the day was over: later workouts are not in yet
        if has_workout or (row is not None and row.get("workout_min") is not None):
            return True
        # between the first and the last logged workout, a day without one is a rest day
        return first_w is not None and first_w <= d <= last_w

    def exercise_on(self, day: date) -> Optional[float]:
        """Workout minutes on ``day`` by the Time page's rule, or None when that day is not known."""
        td = self.time_days().get(day)
        if td is not None:
            return td.value("exercise")
        rows = self.store.rows("workouts")
        starts = [w["start"].date() for w in rows if w["end"] > w["start"]]
        if starts and min(starts) <= day <= max(starts):
            return 0.0
        return None

    def screen_last_day(self) -> Optional[date]:
        days = self.screen_days()
        return max(days) if days else None

    def screen_partial_day(self) -> Optional[date]:
        """The last Screen Time day when imports have stopped arriving: the import most likely cut it off
        part-way (run at 14:00, the evening is not in), so it is not a whole day. None while imports keep coming."""
        last = self.screen_last_day()
        return last if last is not None and last < self.today - timedelta(days=1) else None

    def screen_known_days(self) -> Dict[date, ScreenDay]:
        """Screen days whose record is whole: before today and not the cut-off last import day."""
        partial = self.screen_partial_day()
        return {d: sd for d, sd in self.screen_days().items() if d < self.today and d != partial}

    def fun_before_sleep(self, day: date) -> Optional[float]:
        """Fun minutes in the hour before falling asleep the night after ``day``."""
        body = self.store.by_date("body_daily")
        night = body.get(day + timedelta(days=1)) or {}
        start = night.get("sleep_start")
        if start is None:
            return None
        days = self.screen_days()
        total = 0.0
        t = start - timedelta(minutes=60)
        while t < start:
            sd = days.get(t.date())
            if sd and sd.minutes.get(t.hour * 60 + t.minute) in FUN:
                total += 1
            t += timedelta(minutes=1)
        return total

    def complete_days(self) -> Dict[date, bool]:
        return {row["date"]: row.get("complete") is not False for row in self.store.rows("body_daily")}


def _has_sleep(row: Dict[str, Any]) -> bool:
    return bool(row.get("sleep_start") and row.get("sleep_end") and row["sleep_end"] > row["sleep_start"])


def _longest(minutes: Dict[int, str]) -> float:
    best = run = 0
    gap = 0
    for minute in range(1440):
        if minutes.get(minute) in FOCUS:
            run += 1 + gap
            gap = 0
            best = max(best, run)
        elif run and gap < STRETCH_GAP_MIN:
            gap += 1
        else:
            run = gap = 0
    return float(best)


def iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return value
