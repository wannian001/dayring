"""Apple Health ``export.zip`` / ``export.xml`` -> ``body_daily``, ``workouts`` and ``meals``.

The export is streamed with ``xml.etree.ElementTree.iterparse`` and every top-level element is
cleared once read, so a multi-gigabyte file needs little memory. A zip is read in place (no
extraction). The XML inside is found by content, because its file name is localised on some
phones (``export.xml``, ``导出.xml``, ...).

Rules (each one fixes a mistake that is easy to make with this export):

Time
    Every time string carries the UTC offset of the moment the export was made, not of the
    record. A record may carry ``HKTimeZone`` metadata (the zone the phone was in); it is
    converted to that zone when present, otherwise to the configured timezone. A sleep record
    without the metadata takes the zone of the other records of the same sleep session. Each record is
    filed under the local day of its start; a sleep under the local day you woke up.

Sources
    A source is "watch" when ``sourceName`` or ``device`` mentions "Watch", "phone" when it
    mentions "iPhone", otherwise "other" (third-party apps and other wearables). Priority is
    watch > other > phone.

Sleep (``HKCategoryTypeIdentifierSleepAnalysis``)
    Records of all sources are joined into sessions when the gap between them is at most 60
    minutes. Per session, the asleep minutes come from the highest-priority source that wrote
    asleep records for it (so a watch night is not added to a phone or app estimate of the same
    night); in-bed minutes likewise from the highest-priority source that wrote in-bed records.
    Asleep = Asleep, AsleepCore, AsleepDeep, AsleepREM, AsleepUnspecified; overlapping intervals
    are unioned. When a source wrote both stages and generic "Asleep" for a night, the generic
    record only counts outside the staged span. The main sleep of a wake-up day is its longest
    session; ``sleep_start`` / ``sleep_end`` are its first asleep start and last asleep end.

Steps, exercise minutes and energy burned (active and resting)
    Watch and phone both count the same walk. Samples are taken in priority order; a lower-
    priority sample only counts for the part of its time span that higher-priority samples did
    not already cover (pro rata, the same idea Apple uses). Exact duplicate samples of one
    source family are counted once.

Other columns
    ``hrv_ms`` = daily mean of SDNN, ``resting_hr`` = daily mean, ``vo2max`` = daily mean of the watch's VO2 max
    estimates (mL/kg/min; Apple Watch makes one on some outdoor walks, runs and hikes, so most days have none),
    ``weight_kg`` = last value of the
    day (lb, g and st are converted). Workouts: per day the durations are summed, but a workout
    that overlaps an already-counted one by more than half its length is treated as a copy
    (e.g. the same run written by the watch and by a running app). ``workout_type`` is the
    cleaned activity type of the longest workout. A day on or after the first workout in the
    export that has other data but no workout gets ``workout_min = 0`` (rest day); earlier days,
    and days with no data at all, stay empty.
    ``complete`` is 0 for the export day itself (that day was not over), else 1.

Workouts with their times (``workouts.csv``)
    One row per stretch of moving: a workout paused along the way (``WorkoutEvent`` pause / resume,
    including the watch's auto-pause) is split at its pauses, so the rows add up to the workout's
    duration, as Apple Fitness shows it. When an export has no pause events but the duration is
    clearly shorter than start to end, the row runs from the start for the duration. Copies of one
    workout from two apps are found by their real (UTC) times and written once, from the most
    trusted source. Times are written in the configured timezone, like screen time and the calendar,
    so all of them line up on the day ring (only the day a workout counts for in ``body_daily``
    follows ``HKTimeZone``). Start and end are rounded to the minute and the end is always after
    the start; stretches under 30 seconds and workouts dated before 2000 or after the export are
    left out. ``kcal`` is the workout's active energy when the export has it.

Meals (``meals.csv``)
    Food-logging apps (MyFitnessPal, Lose It!, Cronometer and others) write what you ate into Health as dietary
    records: energy, protein, carbohydrate, fat and fibre, each stamped with the meal's time. Records that start in
    the same minute are one meal; when two apps wrote the same minute, the one with more energy is kept (so one meal
    is never counted twice). The meal comes from a ``meal`` / ``HKFoodMeal`` metadata entry when the app wrote one,
    otherwise from the clock: before 10:30 breakfast, before 15:00 lunch, 17:00 to 21:30 dinner, anything else a
    snack. ``title`` joins up to three ``HKFoodType`` names. kJ become kcal and mg become g. Times are written in
    the configured timezone, like workouts. Re-importing replaces the rows of this export's food apps over the range
    it covers and keeps rows from anywhere else (a hand-typed meal survives).

Workouts also carry ``avg_hr``, the average heart rate the workout's statistics hold (newer exports), and
``effort``, how hard it was on Apple's 1-10 scale (iOS 18 and later): the rating you gave in the Fitness or Workout
app (``WorkoutEffortScore``) when there is one, otherwise the watch's own estimate (``EstimatedWorkoutEffortScore``),
with ``effort_source`` saying which. Apple stores an effort as a sample spanning the workout, so it is matched to the
workout that starts within two minutes of it or that it covers for at least half.

Merge with an existing ``workouts.csv``
    Rows from a source that is in this export (its ``sourceName``) and that start in the export's
    workout range are replaced, since the export holds that source's whole history. Rows from any
    other source (typed by hand, another app's CSV) are kept, unless one overlaps an imported
    workout by more than half of the shorter of the two: that is the same workout, and the copy is
    removed. The summary says how many rows each rule touched.

Merge with an existing ``body_daily.csv``
    Dates not in the export are kept as they are. For a date in the export, each column the
    export has a value for overwrites the old cell; a cell the export has no value for keeps its
    old content, so hand-typed ``waist_cm`` (or a weight typed on a day without a scale reading)
    survives a re-import.
"""
import bisect
import zipfile
from array import array
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Tuple
from xml.etree.ElementTree import iterparse

from ..schema import TABLES
from ._common import Row, Summary, merge_write, span, validate

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"
STEPS = "HKQuantityTypeIdentifierStepCount"
HRV = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
RESTING_HR = "HKQuantityTypeIdentifierRestingHeartRate"
VO2MAX = "HKQuantityTypeIdentifierVO2Max"  # unit "mL/min·kg" (mL per kg per minute)
EXERCISE = "HKQuantityTypeIdentifierAppleExerciseTime"
BODY_MASS = "HKQuantityTypeIdentifierBodyMass"
ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
BASAL_ENERGY = "HKQuantityTypeIdentifierBasalEnergyBurned"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
EFFORT_RATED = "HKQuantityTypeIdentifierWorkoutEffortScore"
EFFORT_ESTIMATED = "HKQuantityTypeIdentifierEstimatedWorkoutEffortScore"
EFFORT_MATCH_S = 120  # an effort sample starting this close to a workout's start belongs to it
DIETARY = {"HKQuantityTypeIdentifierDietaryEnergyConsumed": "kcal", "HKQuantityTypeIdentifierDietaryProtein": "protein_g",
           "HKQuantityTypeIdentifierDietaryCarbohydrates": "carbs_g", "HKQuantityTypeIdentifierDietaryFatTotal": "fat_g",
           "HKQuantityTypeIdentifierDietaryFiber": "fiber_g"}
WANTED = {SLEEP, STEPS, HRV, RESTING_HR, VO2MAX, EXERCISE, BODY_MASS, ACTIVE_ENERGY, BASAL_ENERGY, EFFORT_RATED, EFFORT_ESTIMATED, *DIETARY}
GRAMS = {"g": 1.0, "mg": 0.001, "mcg": 0.000001, "kg": 1000.0, "oz": 28.349523125}
MEAL_WORDS = {"breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner", "supper": "dinner", "snack": "snack",
              "snacks": "snack", "drink": "drink", "drinks": "drink"}

ASLEEP_STAGED = {"HKCategoryValueSleepAnalysisAsleepCore", "HKCategoryValueSleepAnalysisAsleepDeep",
                 "HKCategoryValueSleepAnalysisAsleepREM"}
ASLEEP_GENERIC = {"HKCategoryValueSleepAnalysisAsleep", "HKCategoryValueSleepAnalysisAsleepUnspecified"}
IN_BED = "HKCategoryValueSleepAnalysisInBed"
AWAKE = "HKCategoryValueSleepAnalysisAwake"

FAMILIES = ("watch", "other", "phone")  # priority, highest first
SESSION_GAP = 60 * 60.0                 # seconds between records that still belong to one sleep
MAX_RECORD = 24 * 3600.0                # longer sleep records are broken and skipped
MAX_SESSION = 36 * 3600.0
EARLIEST = date(2000, 1, 1)             # exports contain epoch-0 junk dates

WEIGHT_TO_KG = {"kg": 1.0, "lb": 0.45359237, "lbs": 0.45359237, "g": 0.001, "st": 6.35029318}
DURATION_TO_MIN = {"min": 1.0, "s": 1 / 60.0, "sec": 1 / 60.0, "h": 60.0, "hr": 60.0}
WORKOUT_NAMES = {
    "TraditionalStrengthTraining": "strength training",
    "FunctionalStrengthTraining": "functional strength training",
    "HighIntensityIntervalTraining": "HIIT",
    "MixedCardio": "mixed cardio",
    "CrossTraining": "cross training",
    "MindAndBody": "mind and body",
    "Other": "other",
}

APPLE_COLUMNS = [c.name for c in TABLES["body_daily"].columns if c.name not in ("date", "waist_cm")]


class HealthExportError(ValueError):
    pass


# ---------------------------------------------------------------- reading the file

def open_export(path: Path) -> Tuple[IO[bytes], Optional[zipfile.ZipFile]]:
    """Open the export XML inside a zip, a folder, or as a plain file."""
    path = Path(path)
    if path.is_dir():
        candidates = sorted(p for p in path.rglob("*.xml") if "cda" not in p.name.lower())
        for candidate in candidates:
            with candidate.open("rb") as handle:
                if _looks_like_export(handle.read(4096)):
                    return candidate.open("rb"), None
        raise HealthExportError(f"no Apple Health export.xml found in folder {path}")
    if not path.is_file():
        raise HealthExportError(f"file not found: {path}")
    if zipfile.is_zipfile(path):
        archive = zipfile.ZipFile(path)
        names = [n for n in archive.namelist()
                 if n.lower().endswith(".xml") and "cda" not in n.lower().rsplit("/", 1)[-1]
                 and not n.startswith("__MACOSX")]
        names.sort(key=lambda n: (n.rsplit("/", 1)[-1].lower() != "export.xml", n.count("/"), n))
        for name in names:
            with archive.open(name) as handle:
                if _looks_like_export(handle.read(4096)):
                    return archive.open(name), archive
        archive.close()
        raise HealthExportError(f"{path} is a zip but has no Apple Health export.xml inside")
    return path.open("rb"), None


def _looks_like_export(head: bytes) -> bool:
    return b"HealthData" in head


_OFFSETS: Dict[str, timezone] = {}


def parse_time(text: Optional[str]) -> Optional[datetime]:
    """'2026-10-12 07:50:00 +1100' -> aware datetime. Hand-sliced because strptime is slow
    on millions of records."""
    if not text or len(text) < 25:
        return None
    try:
        offset = text[20:25]
        tz = _OFFSETS.get(offset)
        if tz is None:
            sign = -1 if offset[0] == "-" else 1
            tz = timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5])))
            _OFFSETS[offset] = tz
        return datetime(int(text[0:4]), int(text[5:7]), int(text[8:10]),
                        int(text[11:13]), int(text[14:16]), int(text[17:19]), tzinfo=tz)
    except (ValueError, IndexError):
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None


def _number(text: Optional[str]) -> Optional[float]:
    try:
        value = float(text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def family(source: Optional[str], device: Optional[str]) -> str:
    text = f"{source or ''} {device or ''}"
    if "Watch" in text or "watch" in text:
        return "watch"
    if "iPhone" in text:
        return "phone"
    return "other"


@dataclass
class Collected:
    """Everything kept from one pass over the file, already in local time."""
    export_at: Optional[datetime] = None
    sleep: List[Tuple[float, float, str, str, Any]] = field(default_factory=list)
    # (start_ts, end_ts, value, family, tzinfo from HKTimeZone or None)
    steps: Dict[date, Dict[str, array]] = field(default_factory=lambda: defaultdict(dict))
    exercise: Dict[date, Dict[str, array]] = field(default_factory=lambda: defaultdict(dict))
    active: Dict[date, Dict[str, array]] = field(default_factory=lambda: defaultdict(dict))
    basal: Dict[date, Dict[str, array]] = field(default_factory=lambda: defaultdict(dict))
    # (minute timestamp, source) -> nutrient sums, plus "titles" and "meal" from the metadata
    food: Dict[Tuple[float, str], Dict[str, Any]] = field(default_factory=dict)
    hrv: Dict[date, List[float]] = field(default_factory=lambda: defaultdict(lambda: [0.0, 0]))
    rhr: Dict[date, List[float]] = field(default_factory=lambda: defaultdict(lambda: [0.0, 0]))
    vo2: Dict[date, List[float]] = field(default_factory=lambda: defaultdict(lambda: [0.0, 0]))
    weight: Dict[date, Tuple[float, float]] = field(default_factory=dict)
    workouts: Dict[date, List[Tuple[float, float, float, str, str]]] = field(default_factory=lambda: defaultdict(list))
    sessions: List["Session"] = field(default_factory=list)
    efforts: List[Tuple[float, float, float, bool]] = field(default_factory=list)  # (start_ts, end_ts, 1-10, rated)
    records: int = 0
    skipped: int = 0


@dataclass
class Session:
    """One workout as the export has it. Times are UTC timestamps."""
    start: float
    end: float
    minutes: float                        # HK duration: time moving, pauses excluded
    activity: str
    source: str
    family: str
    segments: List[Tuple[float, float]]   # stretches of moving
    kcal: Optional[float] = None
    avg_hr: Optional[float] = None


PAUSE_EVENTS = {"HKWorkoutEventTypePause", "HKWorkoutEventTypeMotionPaused"}
RESUME_EVENTS = {"HKWorkoutEventTypeResume", "HKWorkoutEventTypeMotionResumed"}
ENERGY_TO_KCAL = {"kcal": 1.0, "Cal": 1.0, "kJ": 0.239005736, "cal": 0.001}
MIN_STRETCH_S = 30.0


class _Zones:
    def __init__(self, default):
        self.default = default
        self.cache: Dict[str, Any] = {}
        self.unknown: Dict[str, int] = {}

    def explicit(self, name: Optional[str]):
        """The zone named by HKTimeZone, or None when absent or unknown."""
        if not name:
            return None
        zone = self.cache.get(name, False)
        if zone is False:
            try:
                zone = ZoneInfo(name)
            except Exception:  # ZoneInfoNotFoundError, ValueError on odd names
                zone = None
            self.cache[name] = zone
        if zone is None:
            self.unknown[name] = self.unknown.get(name, 0) + 1
        return zone


def _hk_timezone(elem) -> Optional[str]:
    for child in elem:
        if child.tag == "MetadataEntry" and child.get("key") == "HKTimeZone":
            return child.get("value")
    return None


def collect(stream: IO[bytes], tz) -> Tuple[Collected, Dict[str, int]]:
    out = Collected()
    zones = _Zones(tz)
    depth = 0
    root = None
    for event, elem in iterparse(stream, events=("start", "end")):
        if event == "start":
            depth += 1
            if root is None:
                root = elem
            continue
        depth -= 1
        if depth != 1:
            continue  # nested element; handled with its parent
        tag = elem.tag
        if tag == "Record":
            kind = elem.get("type")
            if kind in WANTED:
                out.records += 1
                _record(out, elem, kind, zones)
        elif tag == "Workout":
            out.records += 1
            _workout(out, elem, zones)
        elif tag == "ExportDate":
            out.export_at = parse_time(elem.get("value"))
        root.clear()  # type: ignore[union-attr]
    return out, zones.unknown


def _local(elem, zones: _Zones) -> Tuple[Optional[datetime], Optional[datetime], Any]:
    """(start, end, zone from HKTimeZone or None)."""
    start, end = parse_time(elem.get("startDate")), parse_time(elem.get("endDate"))
    return start, end, zones.explicit(_hk_timezone(elem))


def _record(out: Collected, elem, kind: str, zones: _Zones) -> None:
    start, end, explicit = _local(elem, zones)
    if start is None or end is None or end < start:
        out.skipped += 1
        return
    zone = explicit or zones.default
    fam = family(elem.get("sourceName"), elem.get("device"))
    if kind == SLEEP:
        if (end - start).total_seconds() <= MAX_RECORD:
            out.sleep.append((start.timestamp(), end.timestamp(), elem.get("value") or "", fam, explicit))
        else:
            out.skipped += 1
        return
    value = _number(elem.get("value"))
    if value is None:
        out.skipped += 1
        return
    day = start.astimezone(zone).date()
    if kind in DIETARY:
        _food(out, elem, kind, start, value)
        return
    if kind in (EFFORT_RATED, EFFORT_ESTIMATED):
        if 1 <= value <= 10:
            out.efforts.append((start.timestamp(), end.timestamp(), value, kind == EFFORT_RATED))
        else:
            out.skipped += 1
        return
    if kind in (ACTIVE_ENERGY, BASAL_ENERGY):
        factor = ENERGY_TO_KCAL.get(elem.get("unit") or "kcal")
        if factor is None:
            out.skipped += 1
            return
        value *= factor
    if kind in (STEPS, EXERCISE, ACTIVE_ENERGY, BASAL_ENERGY):
        bucket = {STEPS: out.steps, EXERCISE: out.exercise, ACTIVE_ENERGY: out.active, BASAL_ENERGY: out.basal}[kind][day]
        samples = bucket.get(fam)
        if samples is None:
            samples = bucket[fam] = array("d")
        samples.extend((start.timestamp(), end.timestamp(), value))
    elif kind == HRV:
        acc = out.hrv[day]
        acc[0] += value
        acc[1] += 1
    elif kind == RESTING_HR:
        acc = out.rhr[day]
        acc[0] += value
        acc[1] += 1
    elif kind == VO2MAX:
        if not 10 <= value <= 90:  # mL/kg/min; anything else is not a watch estimate
            out.skipped += 1
            return
        acc = out.vo2[day]
        acc[0] += value
        acc[1] += 1
    elif kind == BODY_MASS:
        factor = WEIGHT_TO_KG.get((elem.get("unit") or "kg").lower())
        if factor is None:
            out.skipped += 1
            return
        moment = start.timestamp()
        if day not in out.weight or moment >= out.weight[day][0]:
            out.weight[day] = (moment, value * factor)


def _food(out: Collected, elem, kind: str, start: datetime, value: float) -> None:
    column = DIETARY[kind]
    unit = elem.get("unit") or ("kcal" if column == "kcal" else "g")
    factor = ENERGY_TO_KCAL.get(unit) if column == "kcal" else GRAMS.get(unit.lower())
    if factor is None:
        out.skipped += 1
        return
    key = (round(start.timestamp() / 60.0) * 60.0, elem.get("sourceName") or "")
    meal = out.food.setdefault(key, {"titles": [], "meal": None})
    meal[column] = meal.get(column, 0.0) + value * factor
    for child in elem:
        if child.tag != "MetadataEntry":
            continue
        name, text = (child.get("key") or "").lower(), (child.get("value") or "").strip()
        if name == "hkfoodtype" and text and text not in meal["titles"]:
            meal["titles"].append(text)
        elif name in ("meal", "hkfoodmeal", "hkmealtype") and text.lower() in MEAL_WORDS:
            meal["meal"] = MEAL_WORDS[text.lower()]


def _workout(out: Collected, elem, zones: _Zones) -> None:
    start, end, explicit = _local(elem, zones)
    zone = explicit or zones.default
    if start is None or end is None or end < start:
        out.skipped += 1
        return
    minutes = _number(elem.get("duration"))
    if minutes is not None:
        minutes *= DURATION_TO_MIN.get((elem.get("durationUnit") or "min").lower(), 1.0)
    else:
        minutes = (end - start).total_seconds() / 60
    activity = (elem.get("workoutActivityType") or "").replace("HKWorkoutActivityType", "")
    day = start.astimezone(zone).date()
    fam = family(elem.get("sourceName"), elem.get("device"))
    t0, t1 = start.timestamp(), end.timestamp()
    out.workouts[day].append((t0, t1, minutes, activity, fam))
    events: List[Tuple[float, bool]] = []
    kcal: Optional[float] = None
    avg_hr: Optional[float] = None
    for child in elem:
        if child.tag == "WorkoutEvent" and child.get("type") in PAUSE_EVENTS | RESUME_EVENTS:
            at = parse_time(child.get("date") or child.get("startDate"))
            if at is not None:
                events.append((at.timestamp(), child.get("type") in PAUSE_EVENTS))
        elif child.tag == "WorkoutStatistics" and child.get("type") == ACTIVE_ENERGY:
            value, factor = _number(child.get("sum")), ENERGY_TO_KCAL.get(child.get("unit") or "kcal")
            if value is not None and factor is not None:
                kcal = value * factor
        elif child.tag == "WorkoutStatistics" and child.get("type") == HEART_RATE:
            avg_hr = _number(child.get("average"))
    if kcal is None:  # older exports keep it on the workout itself
        value = _number(elem.get("totalEnergyBurned"))
        factor = ENERGY_TO_KCAL.get(elem.get("totalEnergyBurnedUnit") or "kcal")
        if value is not None and factor is not None and value > 0:
            kcal = value * factor
    out.sessions.append(Session(t0, t1, minutes, activity, elem.get("sourceName") or fam, fam,
                                moving(t0, t1, events, minutes), kcal, avg_hr))


def effort_for(item: "Session", efforts: List[Tuple[float, float, float, bool]]) -> Optional[Tuple[float, str]]:
    """(1-10, "rated" | "estimated") for a workout: your own rating first, else the watch's estimate. An effort
    sample belongs to the workout it starts within EFFORT_MATCH_S of, or covers for at least half."""
    span = max(item.end - item.start, 1.0)
    best: Optional[Tuple[bool, float, float]] = None  # (rated, -distance, value)
    for start, end, value, rated in efforts:
        overlap = min(end, item.end) - max(start, item.start)
        if abs(start - item.start) > EFFORT_MATCH_S and overlap < 0.5 * span:
            continue
        key = (rated, -abs(start - item.start), value)
        if best is None or key[:2] > best[:2]:
            best = key
    if best is None:
        return None
    return round(best[2], 1), "rated" if best[0] else "estimated"


def moving(start: float, end: float, events: List[Tuple[float, bool]], minutes: Optional[float]) -> List[Tuple[float, float]]:
    """The stretches of a workout between its pauses. ``events`` are (time, is_pause)."""
    pauses: List[Tuple[float, float]] = []
    paused_at: Optional[float] = None
    for at, is_pause in sorted(events):
        at = min(max(at, start), end)
        if is_pause and paused_at is None:
            paused_at = at
        elif not is_pause and paused_at is not None:
            if at > paused_at:
                pauses.append((paused_at, at))
            paused_at = None
    if paused_at is not None and end > paused_at:
        pauses.append((paused_at, end))
    stretches: List[Tuple[float, float]] = []
    cursor = start
    for low, high in _merge(pauses):
        if low > cursor:
            stretches.append((cursor, low))
        cursor = max(cursor, high)
    if end > cursor or not stretches:
        stretches.append((cursor, max(cursor, end)))
    if not pauses and minutes is not None and minutes * 60 < (end - start) - 60:
        stretches = [(start, start + minutes * 60)]  # paused, but the export does not say when
    joined: List[Tuple[float, float]] = []
    for low, high in stretches:  # a pause under a minute is not worth a row of its own
        if joined and low - joined[-1][1] < 60:
            joined[-1] = (joined[-1][0], high)
        else:
            joined.append((low, high))
    return joined


# ---------------------------------------------------------------- daily numbers

def _merge(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    merged: List[Tuple[float, float]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _overlap(start: float, end: float, merged: List[Tuple[float, float]], starts: List[float]) -> float:
    index = max(0, bisect.bisect_right(starts, start) - 1)
    total = 0.0
    while index < len(merged) and merged[index][0] < end:
        low, high = max(merged[index][0], start), min(merged[index][1], end)
        if high > low:
            total += high - low
        index += 1
    return total


def _inside(moment: float, merged: List[Tuple[float, float]], starts: List[float]) -> bool:
    index = bisect.bisect_right(starts, moment) - 1
    return index >= 0 and merged[index][0] <= moment <= merged[index][1]


def dedup_sum(by_family: Dict[str, array]) -> float:
    """Sum samples, letting higher-priority families claim the time they cover (see module doc)."""
    total = 0.0
    covered: List[Tuple[float, float]] = []
    for fam in FAMILIES:
        flat = by_family.get(fam)
        if not flat:
            continue
        samples = sorted(set((flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)))
        starts = [s for s, _ in covered]
        for start, end, value in samples:
            if not covered:
                total += value
            elif end <= start:
                total += 0.0 if _inside(start, covered, starts) else value
            else:
                total += value * max(0.0, 1.0 - _overlap(start, end, covered, starts) / (end - start))
        covered = _merge(covered + [(s, e) for s, e, _ in samples])
    return total


@dataclass
class Night:
    day: date
    asleep_min: Optional[float]
    in_bed_min: Optional[float]
    start: Optional[datetime]
    end: Optional[datetime]


def _sessions(records: List[Tuple[float, float, str, str, Any]]) -> List[List[Tuple[float, float, str, str, Any]]]:
    groups: List[List[Tuple[float, float, str, str, Any]]] = []
    group_start = group_end = 0.0
    for record in sorted(records, key=lambda r: (r[0], r[1])):
        start, end = record[0], record[1]
        if not groups or start - group_end > SESSION_GAP or end - group_start > MAX_SESSION:
            groups.append([])
            group_start, group_end = start, end
        groups[-1].append(record)
        group_end = max(group_end, end)
    return groups


def _asleep_intervals(records) -> List[Tuple[float, float, Any]]:
    """Asleep intervals of one source family in one session, generic sleep only outside staged span."""
    staged = [(r[0], r[1], r[4]) for r in records if r[2] in ASLEEP_STAGED]
    generic = [(r[0], r[1], r[4]) for r in records if r[2] in ASLEEP_GENERIC]
    if staged:
        lo = min(s for s, _, _ in staged)
        hi = max(e for _, e, _ in staged)
        outside = []
        for start, end, zone in generic:
            if start < lo:
                outside.append((start, min(end, lo), zone))
            if end > hi:
                outside.append((max(start, hi), end, zone))
        generic = outside
    return [item for item in staged + generic if item[1] > item[0]]


def nights(records: List[Tuple[float, float, str, str, Any]], tz) -> Dict[date, Night]:
    """Main sleep per wake-up day. Records without a zone take the session's zone, else ``tz``."""
    best: Dict[date, Tuple[float, Night]] = {}
    for session in _sessions(records):
        known = [r[4] for r in session if r[4] is not None]
        zone = known[-1] if known else tz
        session = [r if r[4] is not None else (r[0], r[1], r[2], r[3], zone) for r in session]
        asleep: List[Tuple[float, float, Any]] = []
        for fam in FAMILIES:
            asleep = _asleep_intervals([r for r in session if r[3] == fam])
            if asleep:
                break
        beds: List[Tuple[float, float, Any]] = []
        for fam in FAMILIES:
            beds = [(r[0], r[1], r[4]) for r in session if r[3] == fam and r[2] == IN_BED and r[1] > r[0]]
            if beds:
                break
        if not asleep and not beds:
            continue
        asleep_min = sum(e - s for s, e in _merge([(s, e) for s, e, _ in asleep])) / 60 if asleep else None
        bed_min = sum(e - s for s, e in _merge([(s, e) for s, e, _ in beds])) / 60 if beds else None
        basis = asleep or beds
        first = min(basis, key=lambda item: item[0])
        last = max(basis, key=lambda item: item[1])
        end_local = datetime.fromtimestamp(last[1], timezone.utc).astimezone(last[2])
        start_local = datetime.fromtimestamp(first[0], timezone.utc).astimezone(first[2])
        night = Night(day=end_local.date(), asleep_min=asleep_min, in_bed_min=bed_min,
                      start=start_local.replace(tzinfo=None) if asleep else None,
                      end=end_local.replace(tzinfo=None) if asleep else None)
        score = asleep_min if asleep_min is not None else (bed_min or 0.0)
        if night.day not in best or score > best[night.day][0]:
            best[night.day] = (score, night)
    return {day: night for day, (_, night) in best.items()}


def workout_day(items: List[Tuple[float, float, float, str, str]]) -> Tuple[float, str]:
    """(minutes, type of the longest). Copies of the same workout from two apps count once."""
    kept: List[Tuple[float, float, float, str]] = []
    rank = {fam: i for i, fam in enumerate(FAMILIES)}
    for start, end, minutes, activity, fam in sorted(items, key=lambda w: (rank[w[4]], -w[2], w[0])):
        span_s = max(end - start, 1.0)
        duplicate = any(min(end, k_end) - max(start, k_start) > 0.5 * min(span_s, max(k_end - k_start, 1.0))
                        for k_start, k_end, _, _ in kept)
        if not duplicate:
            kept.append((start, end, minutes, activity))
    total = sum(k[2] for k in kept)
    longest = max(kept, key=lambda k: k[2])[3] if kept else ""
    return total, clean_workout_type(longest)


def clean_workout_type(name: str) -> str:
    name = name.replace("HKWorkoutActivityType", "")
    if not name:
        return ""
    if name in WORKOUT_NAMES:
        return WORKOUT_NAMES[name]
    words: List[str] = []
    for ch in name:
        if ch.isupper() and words and not words[-1][-1:].isupper():
            words.append(ch)
        elif words:
            words[-1] += ch
        else:
            words.append(ch)
    return " ".join(w.lower() for w in words)


def build_rows(data: Collected, tz) -> List[Row]:
    export_day = data.export_at.astimezone(tz).date() if data.export_at else None
    sleep = nights(data.sleep, tz)
    days = set(sleep) | set(data.steps) | set(data.exercise) | set(data.hrv) | set(data.rhr) | set(data.vo2) | \
        set(data.weight) | set(data.workouts) | set(data.active) | set(data.basal)
    first_workout = min(data.workouts) if data.workouts else None
    rows: List[Row] = []
    for day in sorted(days):
        if day < EARLIEST or (export_day is not None and day > export_day):
            continue
        row: Row = {name: None for name in [c.name for c in TABLES["body_daily"].columns]}
        row["date"] = day
        night = sleep.get(day)
        if night:
            row.update(sleep_min=night.asleep_min, in_bed_min=night.in_bed_min,
                       sleep_start=night.start, sleep_end=night.end)
        if day in data.hrv:
            total, count = data.hrv[day]
            row["hrv_ms"] = total / count
        if day in data.rhr:
            total, count = data.rhr[day]
            row["resting_hr"] = total / count
        if day in data.vo2:
            total, count = data.vo2[day]
            row["vo2max"] = round(total / count, 1)
        if day in data.steps:
            row["steps"] = float(round(dedup_sum(data.steps[day])))
        if day in data.exercise:
            row["exercise_min"] = dedup_sum(data.exercise[day])
        if day in data.active:
            row["active_kcal"] = float(round(dedup_sum(data.active[day])))
        if day in data.basal:
            row["basal_kcal"] = float(round(dedup_sum(data.basal[day])))
        if day in data.weight:
            row["weight_kg"] = data.weight[day][1]
        if day in data.workouts:
            row["workout_min"], row["workout_type"] = workout_day(data.workouts[day])
            row["workout_type"] = row["workout_type"] or None
        elif first_workout is not None and day >= first_workout:
            row["workout_min"] = 0.0  # the export logs workouts, and this day has data but none
        row["complete"] = export_day is None or day != export_day
        rows.append(row)
    return rows


def _minute(ts: float, tz) -> datetime:
    """A UTC timestamp as local wall-clock time in ``tz``, rounded to the minute."""
    moment = datetime.fromtimestamp(round(ts / 60.0) * 60.0, timezone.utc)
    return moment.astimezone(tz).replace(tzinfo=None)


def workout_rows(data: Collected, tz) -> Tuple[List[Row], List[str], int]:
    """Rows for workouts.csv (see the module doc), notes on what was left out, and how many
    workouts the rows hold (a paused workout has one row per stretch).
    Copies of the same workout from two apps count once (the same overlap rule as workout_day,
    on the real times), keeping the copy from the most trusted source."""
    rank = {fam: i for i, fam in enumerate(FAMILIES)}
    export_day = data.export_at.astimezone(tz).date() if data.export_at else None
    kept: List[Session] = []
    junk = short = 0
    for item in sorted(data.sessions, key=lambda w: (rank[w.family], -w.minutes, w.start)):
        day = datetime.fromtimestamp(item.start, timezone.utc).astimezone(tz).date()
        if day < EARLIEST or (export_day is not None and day > export_day):
            junk += 1
            continue
        span_s = max(item.end - item.start, 1.0)
        duplicate = any(min(item.end, k.end) - max(item.start, k.start) > 0.5 * min(span_s, max(k.end - k.start, 1.0))
                        for k in kept)
        if not duplicate:
            kept.append(item)
    rows: List[Row] = []
    written = 0
    for item in sorted(kept, key=lambda w: w.start):
        stretches = [(a, b) for a, b in item.segments if b - a >= MIN_STRETCH_S]
        if not stretches:
            short += 1
            continue
        written += 1
        kind = clean_workout_type(item.activity) or "workout"
        effort = effort_for(item, data.efforts)
        for i, (a, b) in enumerate(stretches):
            low, high = _minute(a, tz), _minute(b, tz)
            if high <= low:  # under a minute after rounding, or the clocks went back during it
                high = low + timedelta(minutes=max(1, round((b - a) / 60.0)))
            rows.append({"start": low, "end": high, "type": kind, "source": item.source,
                         "kcal": round(item.kcal, 1) if item.kcal is not None and i == 0 else None,
                         "avg_hr": round(item.avg_hr) if item.avg_hr else None,
                         "effort": effort[0] if effort else None, "effort_source": effort[1] if effort else None})
    notes = []
    if junk:
        notes.append(f"left out {junk} workout(s) dated before {EARLIEST.year} or after the export")
    if short:
        notes.append(f"left out {short} workout(s) shorter than {int(MIN_STRETCH_S)} seconds")
    return rows, notes, written


def meal_of(moment: datetime) -> str:
    minutes = moment.hour * 60 + moment.minute
    if minutes < 10 * 60 + 30:
        return "breakfast" if minutes >= 4 * 60 else "snack"
    if minutes < 15 * 60:
        return "lunch"
    if 17 * 60 <= minutes < 21 * 60 + 30:
        return "dinner"
    return "snack"


def meal_rows(data: Collected, tz) -> List[Row]:
    """Rows for meals.csv (see the module doc): one per minute with dietary records, from one app."""
    export_day = data.export_at.astimezone(tz).date() if data.export_at else None
    best: Dict[float, Tuple[str, Dict[str, Any]]] = {}
    for (ts, source), meal in data.food.items():
        if ts not in best or (meal.get("kcal") or 0.0) > (best[ts][1].get("kcal") or 0.0):
            best[ts] = (source, meal)
    rows: List[Row] = []
    for ts in sorted(best):
        source, meal = best[ts]
        when = _minute(ts, tz)
        if when.date() < EARLIEST or (export_day is not None and when.date() > export_day):
            continue
        titles = meal["titles"]
        title = "; ".join(titles[:3]) + (" …" if len(titles) > 3 else "") if titles else None
        rows.append({"time": when, "meal": meal["meal"] or meal_of(when), "title": title, "source": source or None,
                     **{k: round(meal[k], 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g") if k in meal}})
    # two minutes that round to the same (time, meal) key keep the larger
    keyed: Dict[Tuple[datetime, str], Row] = {}
    for row in rows:
        key = (row["time"], row["meal"])
        if key not in keyed or (row.get("kcal") or 0) > (keyed[key].get("kcal") or 0):
            keyed[key] = row
    return list(keyed.values())


# ---------------------------------------------------------------- entry points

def read_export(path: Path, tz, sessions: Optional[List[Row]] = None,
                meals: Optional[List[Row]] = None) -> Tuple[List[Row], Summary]:
    """Parse an export into validated body_daily rows (no file is written).
    Pass a list as ``sessions`` to also receive validated workouts rows, and as ``meals`` for meals rows."""
    stream, archive = open_export(Path(path))
    try:
        return read_stream(stream, tz, str(path), sessions, meals)
    finally:
        stream.close()
        if archive is not None:
            archive.close()


def read_stream(stream: IO[bytes], tz, source: str, sessions: Optional[List[Row]] = None,
                meals: Optional[List[Row]] = None) -> Tuple[List[Row], Summary]:
    """``read_export`` for XML that is already open: the phone app's packages come through here (capture.py)."""
    summary = Summary(table="body_daily", source=source)
    data, unknown_zones = collect(stream, tz)
    if data.export_at is None:
        summary.notes.append("export has no ExportDate; every day is marked complete")
    for name, count in sorted(unknown_zones.items()):
        summary.notes.append(f"unknown HKTimeZone {name!r} on {count} record(s); used the configured timezone")
    if data.skipped:
        summary.notes.append(f"skipped {data.skipped} record(s) with unreadable times or values")
    table = TABLES["body_daily"]
    rows: List[Row] = []
    for row in build_rows(data, tz):
        checked = validate(table, row, f"date {row['date']}", summary.problems)
        if checked is not None:
            rows.append(checked)
    summary.imported = len(rows)
    summary.first, summary.last = span(rows, "date")
    if sessions is not None:
        wtable = TABLES["workouts"]
        wrows, wnotes, summary.counts["workouts"] = workout_rows(data, tz)
        summary.notes += wnotes
        for row in wrows:
            checked = validate(wtable, row, f"workout {row['start']}", summary.problems)
            if checked is not None:
                sessions.append(checked)
    if meals is not None:
        mtable = TABLES["meals"]
        for row in meal_rows(data, tz):
            checked = validate(mtable, row, f"meal {row['time']}", summary.problems)
            if checked is not None:
                meals.append(checked)
    return rows, summary


def _combine(old: Dict[str, str], new: Row) -> Row:
    merged: Row = dict(old)
    for name, value in new.items():
        if value is not None:
            merged[name] = value
    return merged


def _overlaps_half(start: datetime, end: datetime, spans: List[Tuple[datetime, datetime]]) -> bool:
    length = max((end - start).total_seconds(), 1.0)
    for low, high in spans:
        shared = (min(end, high) - max(start, low)).total_seconds()
        if shared > 0.5 * min(length, max((high - low).total_seconds(), 1.0)):
            return True
    return False


def import_apple_health(path: Path, cfg) -> Summary:
    sessions: List[Row] = []
    meals: List[Row] = []
    rows, summary = read_export(path, cfg.tz, sessions, meals)
    return write_rows(cfg, rows, sessions, meals, summary)


def write_rows(cfg, rows: List[Row], sessions: List[Row], meals: List[Row], summary: Summary,
               window: Optional[Tuple[datetime, datetime]] = None) -> Summary:
    """Merge what ``read_export`` / ``read_stream`` returned into the three tables.

    An export holds each source's whole history, so a source's workouts and meals are replaced over the range the
    export covers. A package from the phone covers only its ``window`` (local start, end): that range is used instead,
    so a workout deleted on the phone inside the window also leaves the table."""
    target, total, notes = merge_write(cfg.data_dir, "body_daily", rows, combine=_combine)
    summary.path, summary.total = target, total
    summary.notes += notes
    if sessions:
        first, last = window or (min(r["start"] for r in sessions), max(r["start"] for r in sessions))
        sources = {r["source"] for r in sessions if r.get("source")}
        spans = [(r["start"], r["end"]) for r in sessions]
        end_column = TABLES["workouts"].column("end")
        counts = {"replaced": 0, "copies": 0, "kept": 0}

        def drop(key: Dict[str, Any], raw: Dict[str, str]) -> bool:
            if (raw.get("source") or "").strip() in sources:
                # this source's whole history is in the export: its rows in that range are replaced
                if first <= key["start"] <= last:
                    counts["replaced"] += 1
                    return True
                return False
            try:
                end = end_column.parse(raw.get("end"))
            except (ValueError, TypeError):
                end = None
            if end is not None and end > key["start"] and _overlaps_half(key["start"], end, spans):
                counts["copies"] += 1  # the same workout, recorded by another app or typed in
                return True
            counts["kept"] += 1
            return False

        _, wtotal, wnotes = merge_write(cfg.data_dir, "workouts", sessions, drop=drop)
        workouts = summary.counts.get("workouts", len(sessions))
        split = f", {len(sessions)} rows as paused ones are split at their pauses" if workouts != len(sessions) else ""
        summary.notes.append(f"also wrote {workouts} workouts with start and end times to workouts.csv{split} "
                             f"({wtotal} rows in total)")
        summary.notes.append(f"workouts.csv: replaced {counts['replaced']} row(s) from the export's sources, "
                             f"removed {counts['copies']} copy(ies) of imported workouts, "
                             f"kept {counts['kept']} row(s) from other sources")
        summary.notes += wnotes
    if meals:
        first, last = window or (min(r["time"] for r in meals), max(r["time"] for r in meals))
        sources = {r["source"] for r in meals if r.get("source")}
        replaced = [0]

        def drop_meal(key: Dict[str, Any], raw: Dict[str, str]) -> bool:
            # a food app's whole history is in the export: its rows over the export's range are replaced
            if (raw.get("source") or "").strip() in sources and first <= key["time"] <= last:
                replaced[0] += 1
                return True
            return False

        _, mtotal, mnotes = merge_write(cfg.data_dir, "meals", meals, drop=drop_meal)
        summary.notes.append(f"also wrote {len(meals)} meals to meals.csv ({mtotal} rows in total; "
                             f"replaced {replaced[0]} row(s) from the export's food apps)")
        summary.notes += mnotes
    return summary
