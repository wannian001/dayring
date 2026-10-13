"""The data contract: every table dayring reads, defined in one place.

All tables are UTF-8 CSV files with a header row, kept in the data directory
named in ``dayring.toml``. Importers write them; modules only read them.
``docs/DATA_FORMAT.md`` is generated from this file (``python -m dayring schema --markdown``).

Conventions
- ``date``: local calendar day, ``YYYY-MM-DD``.
- ``datetime``: local wall-clock time without offset, ``YYYY-MM-DDTHH:MM`` (seconds optional).
  The timezone is the one in ``dayring.toml``. One exception: ``sleep_start`` / ``sleep_end`` from
  Apple Health are in the zone you slept in, so a night abroad reads as you lived it.
- Minutes are real minutes: on the day clocks go forward the skipped hour is not counted, and a
  record that runs through the repeated hour when they go back counts it twice (23- and 25-hour days).
- Empty cell = unknown. Unknown is never read as zero.
- A sleep belongs to the day you woke up.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

Parser = Callable[[str], Any]


def _date(text: str) -> date:
    return date.fromisoformat(text)


def _datetime(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    if value.tzinfo is not None:
        raise ValueError("datetime must be local wall-clock time without an offset")
    return value


def _float(text: str) -> float:
    value = float(text)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("not a finite number")
    return value


def _flag(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in ("1", "true", "yes"):
        return True
    if lowered in ("0", "false", "no"):
        return False
    raise ValueError("expected 1/0")


def _text(text: str) -> str:
    return text


TYPES: Dict[str, Parser] = {"date": _date, "datetime": _datetime, "number": _float,
                            "flag": _flag, "text": _text}


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    doc: str
    required: bool = False
    choices: Tuple[str, ...] = ()
    low: Optional[float] = None
    high: Optional[float] = None

    def parse(self, raw: str) -> Any:
        if raw is None or raw.strip() == "":
            if self.required:
                raise ValueError(f"{self.name} is required")
            return None
        value = TYPES[self.type](raw.strip())
        if self.choices and value not in self.choices:
            raise ValueError(f"{self.name} must be one of {', '.join(self.choices)}")
        if self.low is not None and value < self.low:
            raise ValueError(f"{self.name} below {self.low}")
        if self.high is not None and value > self.high:
            raise ValueError(f"{self.name} above {self.high}")
        return value


@dataclass(frozen=True)
class Table:
    name: str
    doc: str
    key: Tuple[str, ...]
    columns: Tuple[Column, ...]
    sources: Tuple[str, ...] = field(default_factory=tuple)
    interval: Tuple[str, ...] = ()  # (start, end) columns of a time span; end must be after start

    def interval_problem(self, row: Dict[str, Any]) -> Optional[str]:
        if not self.interval:
            return None
        start, end = (row.get(c) for c in self.interval)
        if start is not None and end is not None and end <= start:
            return f"{self.interval[1]} must be after {self.interval[0]}"
        return None

    @property
    def filename(self) -> str:
        return f"{self.name}.csv"

    def column(self, name: str) -> Column:
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(name)


SCREEN_CATEGORIES = ("work", "learning", "communication", "entertainment", "social", "other")
EVENT_KINDS = ("class", "work", "training", "personal", "other")
DEADLINE_STATUS = ("todo", "submitted", "done")
AI_TOOLS = ("claude_code", "codex", "other")
AI_STARTED_BY = ("you", "scheduled", "script")

TABLES: Dict[str, Table] = {t.name: t for t in (
    Table(
        name="body_daily",
        doc="One row per day of body measurements, usually from a watch or phone.",
        key=("date",),
        sources=("Apple Health export (dayring import apple-health)", "any CSV with these columns"),
        columns=(
            Column("date", "date", "The day. Sleep is filed under the day you woke up.", required=True),
            Column("sleep_min", "number", "Minutes asleep in the main sleep that ended this day.", low=0, high=1440),
            Column("in_bed_min", "number", "Minutes in bed for the same sleep.", low=0, high=1440),
            Column("sleep_start", "datetime", "When you fell asleep (local time)."),
            Column("sleep_end", "datetime", "When you woke up (local time)."),
            Column("hrv_ms", "number", "Heart-rate variability (SDNN or RMSSD, but keep one kind), ms.", low=1, high=400),
            Column("resting_hr", "number", "Resting heart rate, beats per minute.", low=20, high=200),
            Column("steps", "number", "Steps that day.", low=0),
            Column("exercise_min", "number", "Minutes of exercise (Apple 'Exercise' ring or similar).", low=0, high=1440),
            Column("workout_min", "number", "Minutes of logged workouts. 0 means rest day; empty means unknown.", low=0, high=1440),
            Column("workout_type", "text", "Main workout that day, free text (e.g. strength, run)."),
            Column("weight_kg", "number", "Body weight, kg.", low=20, high=400),
            Column("waist_cm", "number", "Waist, cm.", low=30, high=250),
            Column("complete", "flag", "1 if the day was over when the data was exported; 0 if the export happened "
                                         "mid-day (then steps and minutes are not compared with your normal)."),
        ),
    ),
    Table(
        name="workouts",
        doc="Each workout with its start and end, e.g. from Apple Fitness or a watch. The Time page uses the "
            "times; body_daily.workout_min is the daily total. A workout paused along the way can be one row per "
            "stretch of moving (the Apple Health importer writes it so), so the minutes are the time spent moving. "
            "`end` must be after `start`.",
        key=("start", "type"),
        interval=("start", "end"),
        sources=("Apple Health export, which includes Apple Fitness and Workout app sessions (dayring import apple-health)",
                 "Strava, Garmin or any CSV with these columns"),
        columns=(
            Column("start", "datetime", "Start (local time).", required=True),
            Column("end", "datetime", "End (local time).", required=True),
            Column("type", "text", "What kind of workout, e.g. strength training, running.", required=True),
            Column("source", "text", "Which app or device recorded it."),
            Column("kcal", "number", "Active energy for the workout, kcal.", low=0),
        ),
    ),
    Table(
        name="self_report",
        doc="How you said you felt, on a 0–5 scale. Optional; pages show a prompt when it is empty.",
        key=("date",),
        sources=("typed by hand", "an assistant that writes this file for you"),
        columns=(
            Column("date", "date", "The day.", required=True),
            Column("energy", "number", "Body energy, 0 (drained) to 5 (full).", low=0, high=5),
            Column("focus", "number", "Mental focus, 0 to 5.", low=0, high=5),
            Column("note", "text", "One line in your own words."),
        ),
    ),
    Table(
        name="screen_sessions",
        doc="Foreground app sessions across your devices. Overlaps between devices are allowed; "
            "dayring counts wall-clock time once, preferring the device order in dayring.toml "
            "(the Time page's devices-at-once card counts each device on its own). "
            "`end` must be after `start`.",
        key=("start", "device", "app"),
        interval=("start", "end"),
        sources=("macOS Screen Time / Biome (dayring import macos-screentime)", "RescueTime or ActivityWatch CSV",
                 "any CSV with these columns"),
        columns=(
            Column("start", "datetime", "Session start (local time).", required=True),
            Column("end", "datetime", "Session end (local time).", required=True),
            Column("device", "text", "Device name, e.g. laptop, phone, tablet.", required=True),
            Column("app", "text", "App name or website domain.", required=True),
            Column("category", "text", "What kind of use it was.", required=True, choices=SCREEN_CATEGORIES),
        ),
    ),
    Table(
        name="events",
        doc="Calendar blocks: classes, work shifts, planned training.",
        key=("start", "title"),
        sources=("any .ics calendar (dayring import ics)", "any CSV with these columns"),
        columns=(
            Column("start", "datetime", "Start (local time).", required=True),
            Column("end", "datetime", "End (local time).", required=True),
            Column("title", "text", "What it is.", required=True),
            Column("kind", "text", "Type of block.", required=True, choices=EVENT_KINDS),
            Column("location", "text", "Where."),
        ),
    ),
    Table(
        name="deadlines",
        doc="Things due on a date: assignments, exams, milestones.",
        key=("due", "title"),
        sources=("typed by hand", "a course or project tracker export"),
        columns=(
            Column("due", "datetime", "When it is due (local time). Use 23:59 if only the day is known.", required=True),
            Column("title", "text", "What is due.", required=True),
            Column("group", "text", "Course or project it belongs to."),
            Column("weight_pct", "number", "Share of the course grade, percent. Empty if it is not graded.", low=0, high=100),
            Column("status", "text", "Where it stands.", choices=DEADLINE_STATUS),
            Column("note", "text", "Format, length, group size, anything you want to see next to it."),
        ),
    ),
    Table(
        name="ai_work",
        doc="Stretches when an AI coding agent was working for you: model calls of one session no more than "
            "5 minutes apart. Several sessions at once each count, like several people working. Only times, "
            "counts and model token totals; never what was said. A tool busy for over 5 minutes between two "
            "calls is missed, so it is a lower bound.",
        key=("start", "tool", "session"),
        interval=("start", "end"),
        sources=("Claude Code and Codex logs on this computer (dayring import ai-logs)", "any CSV with these columns"),
        columns=(
            Column("start", "datetime", "First call of the stretch (local time, rounded down to the minute).", required=True),
            Column("end", "datetime", "Last call of the stretch (local time, rounded up to the minute).", required=True),
            Column("tool", "text", "Which agent.", required=True, choices=AI_TOOLS),
            Column("session", "text", "A short code for the session (a hash, never the tool's own id).", required=True),
            Column("started_by", "text", "Who started the session: you, a scheduled task or a script "
                   "(claude -p, codex exec). Only yours count as your AI work.", required=True, choices=AI_STARTED_BY),
            Column("minutes", "number", "Minutes of work inside the stretch (exact; start and end are rounded).",
                   required=True, low=0),
            Column("calls", "number", "Model calls in the stretch.", low=0),
            Column("output_tokens", "number", "Tokens the model wrote in the stretch.", low=0),
        ),
    ),
    Table(
        name="ai_prompts",
        doc="The instructions you typed to an AI coding agent, counted per minute. Only the time; never the text.",
        key=("time", "tool", "session"),
        sources=("Claude Code and Codex logs on this computer (dayring import ai-logs)", "any CSV with these columns"),
        columns=(
            Column("time", "datetime", "The minute (local time).", required=True),
            Column("tool", "text", "Which agent.", required=True, choices=AI_TOOLS),
            Column("session", "text", "A short code for the session (a hash, never the tool's own id).", required=True),
            Column("started_by", "text", "Who started the session.", required=True, choices=AI_STARTED_BY),
            Column("count", "number", "Instructions in that minute.", required=True, low=1),
        ),
    ),
)}


def describe_markdown() -> str:
    """The reference page in docs/DATA_FORMAT.md, generated so it never drifts from the code."""
    lines: List[str] = [
        "# Data format",
        "",
        "<!-- generated by `python -m dayring schema --markdown`; edit dayring/schema.py instead -->",
        "",
        __doc__.split("\n\n", 1)[1].strip(),
        "",
    ]
    for table in TABLES.values():
        lines += [f"## `{table.filename}`", "", table.doc, "",
                  f"Key: {', '.join('`%s`' % k for k in table.key)}. "
                  f"Typical sources: {'; '.join(table.sources) or 'any CSV'}.", "",
                  "| column | type | required | meaning |", "|---|---|---|---|"]
        for col in table.columns:
            extra = f" One of: {', '.join('`%s`' % c for c in col.choices)}." if col.choices else ""
            lines.append(f"| `{col.name}` | {col.type} | {'yes' if col.required else ''} | {col.doc}{extra} |")
        lines.append("")
    return "\n".join(lines)
