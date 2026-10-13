"""iCalendar (.ics) -> ``events``. Standard library only.

Handles what calendar exports and university timetables use:

- line unfolding, escaped text (``\\,`` ``\\;`` ``\\n``), components nested in VEVENT (VALARM) ignored;
- ``DTSTART`` / ``DTEND`` as UTC (``...Z``), with ``TZID=`` (IANA names, the common Windows names
  Outlook writes, ``X-LIC-LOCATION`` in the file's VTIMEZONE, or a ``(UTC+10:00) ...`` label as a
  fixed offset), or floating (read as the configured timezone);
- ``DURATION`` instead of ``DTEND``;
- ``RRULE`` with ``FREQ=DAILY`` or ``FREQ=WEEKLY``, ``INTERVAL``, ``COUNT``, ``UNTIL``, ``BYDAY``,
  ``WKST``; repeats are computed on the event's own wall clock, so a 10:00 class stays at 10:00
  across a daylight-saving change; ``RDATE`` and ``EXDATE`` (several values or lines);
- overridden instances (a VEVENT with the same ``UID`` and a ``RECURRENCE-ID``), including
  cancelled ones (``STATUS:CANCELLED``).

All-day events (``VALUE=DATE``) are skipped by default because they are not time blocks; with
``include_all_day=True`` they become 00:00-23:59 rows (multi-day ones span from the first day
00:00 to the last day 23:59). Other recurrence frequencies (MONTHLY, YEARLY) are not expanded:
only the first instance is kept and a problem is reported.

Instances are kept when they overlap the window (default 180 days back to 180 days ahead).
``kind`` comes from keyword rules on the title (whole words, optional plural "s"), or one kind
is forced for the whole file.

Merge rule: re-importing a calendar replaces its events inside the window. An existing row inside
the window whose title also appears in this file is removed first; rows outside the window and
rows with other titles (another calendar, typed by hand) are kept.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from ..schema import EVENT_KINDS, TABLES
from ._common import Row, Summary, merge_write, span, validate

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

DEFAULT_KIND_RULES: List[Tuple[str, List[str]]] = [
    ("class", ["lecture", "lec", "tutorial", "tut", "workshop", "practical", "prac", "seminar",
               "class", "lab", "laboratory"]),
    ("training", ["gym", "run", "running", "workout", "training"]),
]
DEFAULT_DAYS_BACK = 180
DEFAULT_DAYS_AHEAD = 180
MAX_INSTANCES = 20000  # per recurring event, a guard against runaway rules

WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}

# Windows zone names written by Outlook / Exchange -> IANA (common ones only).
WINDOWS_ZONES = {
    "AUS Eastern Standard Time": "Australia/Sydney", "E. Australia Standard Time": "Australia/Brisbane",
    "Cen. Australia Standard Time": "Australia/Adelaide", "AUS Central Standard Time": "Australia/Darwin",
    "W. Australia Standard Time": "Australia/Perth", "Tasmania Standard Time": "Australia/Hobart",
    "New Zealand Standard Time": "Pacific/Auckland", "China Standard Time": "Asia/Shanghai",
    "Taipei Standard Time": "Asia/Taipei", "Tokyo Standard Time": "Asia/Tokyo",
    "Korea Standard Time": "Asia/Seoul", "Singapore Standard Time": "Asia/Singapore",
    "SE Asia Standard Time": "Asia/Bangkok", "India Standard Time": "Asia/Kolkata",
    "Arabian Standard Time": "Asia/Dubai", "Israel Standard Time": "Asia/Jerusalem",
    "Turkey Standard Time": "Europe/Istanbul", "Russian Standard Time": "Europe/Moscow",
    "GMT Standard Time": "Europe/London", "Greenwich Standard Time": "Atlantic/Reykjavik",
    "W. Europe Standard Time": "Europe/Berlin", "Romance Standard Time": "Europe/Paris",
    "Central Europe Standard Time": "Europe/Budapest", "Central European Standard Time": "Europe/Warsaw",
    "E. Europe Standard Time": "Europe/Chisinau", "FLE Standard Time": "Europe/Helsinki",
    "GTB Standard Time": "Europe/Bucharest", "South Africa Standard Time": "Africa/Johannesburg",
    "Egypt Standard Time": "Africa/Cairo", "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago", "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix", "Pacific Standard Time": "America/Los_Angeles",
    "Alaskan Standard Time": "America/Anchorage", "Hawaiian Standard Time": "Pacific/Honolulu",
    "Atlantic Standard Time": "America/Halifax", "Canada Central Standard Time": "America/Regina",
    "SA Pacific Standard Time": "America/Bogota", "E. South America Standard Time": "America/Sao_Paulo",
    "Argentina Standard Time": "America/Buenos_Aires", "UTC": "UTC", "Coordinated Universal Time": "UTC",
}


# ---------------------------------------------------------------- parsing

@dataclass
class Prop:
    name: str
    params: Dict[str, str]
    value: str


@dataclass
class Component:
    name: str
    props: List[Prop] = field(default_factory=list)
    children: List["Component"] = field(default_factory=list)

    def get(self, name: str) -> Optional[Prop]:
        for prop in self.props:
            if prop.name == name:
                return prop
        return None

    def all(self, name: str) -> List[Prop]:
        return [p for p in self.props if p.name == name]


def unfold(text: str) -> List[str]:
    lines: List[str] = []
    for line in re.split(r"\r\n|\n|\r", text):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return [line for line in lines if line.strip()]


def _split_outside_quotes(text: str, sep: str) -> List[str]:
    parts, current, quoted = [], [], False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == sep and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def parse_line(line: str) -> Optional[Prop]:
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            head, value = line[:i], line[i + 1:]
            break
    else:
        return None
    pieces = _split_outside_quotes(head, ";")
    params: Dict[str, str] = {}
    for piece in pieces[1:]:
        if "=" in piece:
            key, val = piece.split("=", 1)
            params[key.strip().upper()] = val.strip().strip('"')
    return Prop(pieces[0].strip().upper(), params, value)


def parse_calendar(text: str) -> Component:
    root = Component("ROOT")
    stack = [root]
    for line in unfold(text.lstrip("﻿")):
        prop = parse_line(line)
        if prop is None:
            continue
        if prop.name == "BEGIN":
            child = Component(prop.value.strip().upper())
            stack[-1].children.append(child)
            stack.append(child)
        elif prop.name == "END":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].props.append(prop)
    return root


def walk(component: Component, name: str) -> Iterator[Component]:
    for child in component.children:
        if child.name == name:
            yield child
        else:
            yield from walk(child, name)


def unescape(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append("\n" if nxt in "nN" else nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out).strip()


# ---------------------------------------------------------------- time values

class Zones:
    """Resolves TZID values; remembers the ones it had to guess."""

    def __init__(self, default, vtimezones: Optional[Dict[str, str]] = None):
        self.default = default
        self.locations = vtimezones or {}
        self.cache: Dict[str, Any] = {}
        self.guessed: Dict[str, str] = {}

    def get(self, tzid: Optional[str]):
        if not tzid:
            return self.default
        if tzid not in self.cache:
            self.cache[tzid] = self._resolve(tzid)
        return self.cache[tzid]

    def _resolve(self, tzid: str):
        name = tzid.strip().strip('"')
        for candidate in (name, self.locations.get(name), WINDOWS_ZONES.get(name)):
            zone = _zoneinfo(candidate)
            if zone is not None:
                return zone
        tail = re.search(r"([A-Za-z_]+/[A-Za-z_+\-]+(?:/[A-Za-z_+\-]+)?)$", name)
        if tail and _zoneinfo(tail.group(1)) is not None:
            return _zoneinfo(tail.group(1))
        fixed = re.search(r"(?:UTC|GMT)\s*([+-])(\d{1,2}):?(\d{2})?", name)
        if fixed:
            sign = -1 if fixed.group(1) == "-" else 1
            offset = timedelta(hours=int(fixed.group(2)), minutes=int(fixed.group(3) or 0))
            self.guessed[name] = "fixed offset from its label (daylight saving ignored)"
            return timezone(sign * offset)
        self.guessed[name] = "unknown, read as the configured timezone"
        return self.default


def _zoneinfo(name: Optional[str]):
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception:  # ZoneInfoNotFoundError, ValueError
        return None


def parse_value(value: str, params: Dict[str, str], zones: Zones) -> Any:
    """-> date (all-day) or aware datetime."""
    value = value.strip()
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z?)", value)
    if not match:
        raise ValueError(f"cannot read date-time {value!r}")
    parts = [int(g) for g in match.groups()[:5]] + [int(match.group(6) or 0)]
    naive = datetime(*parts)
    if match.group(7):
        return naive.replace(tzinfo=timezone.utc)
    return naive.replace(tzinfo=zones.get(params.get("TZID")))


def parse_duration(text: str) -> timedelta:
    match = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", text.strip())
    if not match:
        raise ValueError(f"cannot read duration {text!r}")
    weeks, days, hours, minutes, seconds = (int(g or 0) for g in match.groups()[1:])
    delta = timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)
    return -delta if match.group(1) == "-" else delta


def _values(props: List[Prop], zones: Zones) -> List[Any]:
    out = []
    for prop in props:
        for piece in prop.value.split(","):
            if piece.strip():
                out.append(parse_value(piece, prop.params, zones))
    return out


def _instant_key(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# ---------------------------------------------------------------- recurrence

def parse_rrule(text: str) -> Dict[str, str]:
    rule: Dict[str, str] = {}
    for piece in text.split(";"):
        if "=" in piece:
            key, val = piece.split("=", 1)
            rule[key.strip().upper()] = val.strip().upper()
    return rule


def recurrence(start: Any, rule: Dict[str, str], zones: Zones, until_limit: Any,
               from_day: Optional[date] = None) -> Tuple[List[Any], Optional[str]]:
    """Start values of a recurring event, in the event's own zone, up to ``until_limit``
    (same type as ``start``). Without COUNT, repeats long before ``from_day`` are skipped
    arithmetically, so an old open-ended rule stays cheap. Returns (starts, problem)."""
    freq = rule.get("FREQ", "")
    if freq not in ("DAILY", "WEEKLY"):
        return [start], f"RRULE FREQ={freq or '?'} is not supported; only the first instance is kept"
    interval = max(1, int(rule.get("INTERVAL", "1") or 1))
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = None
    if rule.get("UNTIL"):
        until = parse_value(rule["UNTIL"], {}, zones)
        if isinstance(start, datetime) and isinstance(until, date) and not isinstance(until, datetime):
            until = datetime.combine(until, time(23, 59, 59), tzinfo=start.tzinfo)
        elif isinstance(start, datetime) and isinstance(until, datetime) and until.tzinfo is not start.tzinfo:
            until = until.astimezone(start.tzinfo)
        elif not isinstance(start, datetime) and isinstance(until, datetime):
            until = until.astimezone(zones.default).date()
    days = [WEEKDAYS[d[-2:]] for d in rule.get("BYDAY", "").split(",") if d[-2:] in WEEKDAYS]
    wkst = WEEKDAYS.get(rule.get("WKST", "MO"), 0)

    is_dt = isinstance(start, datetime)
    tz = start.tzinfo if is_dt else None
    wall = start.replace(tzinfo=None) if is_dt else start
    first_day = wall.date() if is_dt else wall
    clock = wall.time() if is_dt else None

    def make(day: date) -> Any:
        return datetime.combine(day, clock).replace(tzinfo=tz) if is_dt else day

    skip = 0  # whole periods that end before from_day (only safe when COUNT is not used)
    if count is None and from_day is not None and from_day > first_day:
        skip = max(0, ((from_day - first_day).days // (interval * (1 if freq == "DAILY" else 7))) - 1)

    def candidates() -> Iterator[date]:
        if freq == "DAILY":
            day = first_day + timedelta(days=skip * interval)
            while True:
                if not days or day.weekday() in days:
                    yield day
                day += timedelta(days=interval)
        else:
            weekdays = sorted(days or [first_day.weekday()], key=lambda d: (d - wkst) % 7)
            week = first_day - timedelta(days=(first_day.weekday() - wkst) % 7) + timedelta(weeks=skip * interval)
            while True:
                for wd in weekdays:
                    day = week + timedelta(days=(wd - wkst) % 7)
                    if day >= first_day:
                        yield day
                week += timedelta(weeks=interval)

    out = [start]  # DTSTART is always the first instance
    for day in candidates():
        if len(out) >= MAX_INSTANCES or (count is not None and len(out) >= count):
            break
        value = make(day)
        if day == first_day:
            continue
        if until is not None and value > until:
            break
        if value > until_limit:
            break
        out.append(value)
    return out, None


# ---------------------------------------------------------------- events

def classify(title: str, rules: Sequence[Tuple[str, Sequence[str]]]) -> str:
    lowered = title.lower()
    for kind, words in rules:
        for word in words:
            if re.search(r"(?<![a-z])" + re.escape(word.lower()) + r"s?(?![a-z])", lowered):
                return kind
    return "other"


@dataclass
class _Event:
    uid: str
    start: Any
    end: Any
    title: str
    location: Optional[str]
    cancelled: bool
    component: Component


def _event(comp: Component, zones: Zones, problems: List[str], index: int) -> Optional[_Event]:
    dtstart = comp.get("DTSTART")
    if dtstart is None:
        problems.append(f"event {index}: no DTSTART, skipped")
        return None
    try:
        start = parse_value(dtstart.value, dtstart.params, zones)
        dtend, duration = comp.get("DTEND"), comp.get("DURATION")
        if dtend is not None:
            end = parse_value(dtend.value, dtend.params, zones)
        elif duration is not None:
            end = start + parse_duration(duration.value)
        else:
            end = start if isinstance(start, datetime) else start + timedelta(days=1)
        if isinstance(start, datetime) != isinstance(end, datetime):
            end = start + (timedelta(days=1) if not isinstance(start, datetime) else timedelta(0))
        if end < start:
            end = start
    except ValueError as error:
        problems.append(f"event {index}: {error}, skipped")
        return None
    summary = comp.get("SUMMARY")
    location = comp.get("LOCATION")
    status = comp.get("STATUS")
    uid = comp.get("UID")
    return _Event(uid=(uid.value.strip() if uid else f"#{index}"), start=start, end=end,
                  title=unescape(summary.value) if summary and unescape(summary.value) else "(untitled)",
                  location=(unescape(location.value) or None) if location else None,
                  cancelled=bool(status and status.value.strip().upper() == "CANCELLED"), component=comp)


def _local(value: Any, tz) -> datetime:
    return value.astimezone(tz).replace(tzinfo=None, second=0, microsecond=0)


def expand(text: str, tz, window_start: datetime, window_end: datetime, kind: Optional[str] = None,
           rules: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
           include_all_day: bool = False) -> Tuple[List[Row], List[str], List[str]]:
    """Calendar text -> event rows inside [window_start, window_end) (naive local times in ``tz``).
    Returns (rows, problems, notes)."""
    if kind is not None and kind not in EVENT_KINDS:
        raise ValueError(f"kind must be one of {', '.join(EVENT_KINDS)}")
    rules = DEFAULT_KIND_RULES if rules is None else rules
    calendar = parse_calendar(text)
    locations = {}
    for vtz in walk(calendar, "VTIMEZONE"):
        tzid, location = vtz.get("TZID"), vtz.get("X-LIC-LOCATION")
        if tzid and location:
            locations[tzid.value.strip()] = location.value.strip()
    zones = Zones(tz, locations)
    problems: List[str] = []
    notes: List[str] = []

    masters: List[_Event] = []
    overrides: Dict[Tuple[str, Any], _Event] = {}
    for index, comp in enumerate(walk(calendar, "VEVENT"), start=1):
        event = _event(comp, zones, problems, index)
        if event is None:
            continue
        rid = comp.get("RECURRENCE-ID")
        if rid is not None:
            try:
                overrides[(event.uid, _instant_key(parse_value(rid.value, rid.params, zones)))] = event
            except ValueError as error:
                problems.append(f"event {index}: RECURRENCE-ID {error}")
            continue
        masters.append(event)

    hi = window_end.replace(tzinfo=tz)
    master_uids = {m.uid for m in masters}
    instances: List[Tuple[Any, Any, _Event]] = []
    used_overrides: Set[Tuple[str, Any]] = set()
    for event in masters:
        length = event.end - event.start
        starts = [event.start]
        comp = event.component
        rrule = comp.get("RRULE")
        if rrule is not None:
            limit = hi.astimezone(event.start.tzinfo) if isinstance(event.start, datetime) else window_end.date()
            starts, problem = recurrence(event.start, parse_rrule(rrule.value), zones, limit,
                                         from_day=window_start.date() - timedelta(days=1))
            if problem:
                problems.append(f"{event.title!r}: {problem}")
        try:
            starts += [v for v in _values(comp.all("RDATE"), zones)
                       if isinstance(v, datetime) == isinstance(event.start, datetime)]
        except ValueError as error:
            problems.append(f"{event.title!r}: RDATE {error}")
        try:
            excluded = {_instant_key(v) for v in _values(comp.all("EXDATE"), zones)}
        except ValueError as error:
            problems.append(f"{event.title!r}: EXDATE {error}")
            excluded = set()
        for start in sorted(set(starts), key=_instant_key):
            key = _instant_key(start)
            if key in excluded or (isinstance(start, datetime) and start.date() in excluded):
                continue
            override = overrides.get((event.uid, key))
            if override is not None:
                used_overrides.add((event.uid, key))
                if not override.cancelled:
                    instances.append((override.start, override.end, override))
                continue
            if not event.cancelled:
                instances.append((start, start + length, event))
    for key, override in overrides.items():  # an override whose master is not in this file
        if key not in used_overrides and not override.cancelled and key[0] not in master_uids:
            instances.append((override.start, override.end, override))

    rows: List[Row] = []
    skipped_all_day = 0
    for start, end, event in instances:
        if not isinstance(start, datetime):
            if not include_all_day:
                skipped_all_day += 1
                continue
            last_day = (end - timedelta(days=1)) if end > start else start
            row_start = datetime.combine(start, time(0, 0))
            row_end = datetime.combine(last_day, time(23, 59))
        else:
            row_start, row_end = _local(start, tz), _local(end, tz)
        if row_end < window_start or row_start >= window_end:
            continue
        rows.append({"start": row_start, "end": row_end, "title": event.title,
                     "kind": kind or classify(event.title, rules), "location": event.location})
    if skipped_all_day:
        notes.append(f"skipped {skipped_all_day} all-day instance(s) (use --all-day to keep them)")
    for name, how in sorted(zones.guessed.items()):
        notes.append(f"TZID {name!r}: {how}")
    rows.sort(key=lambda r: (r["start"], r["title"]))
    return rows, problems, notes


def read_ics(path: Path) -> str:
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def import_ics(path: Path, cfg, kind: Optional[str] = None, days_back: int = DEFAULT_DAYS_BACK,
               days_ahead: int = DEFAULT_DAYS_AHEAD, include_all_day: bool = False,
               rules: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
               today: Optional[date] = None) -> Summary:
    tz = cfg.tz
    today = today or datetime.now(tz).date()
    window_start = datetime.combine(today - timedelta(days=days_back), time(0, 0))
    window_end = datetime.combine(today + timedelta(days=days_ahead + 1), time(0, 0))
    summary = Summary(table="events", source=str(path))
    rows, problems, notes = expand(read_ics(path), tz, window_start, window_end, kind=kind,
                                   rules=rules, include_all_day=include_all_day)
    summary.problems += problems
    summary.notes += notes
    table = TABLES["events"]
    checked = [r for r in (validate(table, row, f"{row['title']!r} at {row['start']}", summary.problems)
                           for row in rows) if r is not None]
    titles = {r["title"] for r in checked}

    def drop(key: Dict[str, Any], raw: Dict[str, str]) -> bool:
        return key["title"] in titles and window_start <= key["start"] < window_end

    target, total, merge_notes = merge_write(cfg.data_dir, "events", checked, drop=drop)
    summary.imported, summary.total, summary.path = len(checked), total, target
    summary.first, summary.last = span(checked, "start")
    summary.notes += merge_notes
    return summary
