"""Small, explainable statistics shared by every page.

"Your normal" is always you compared with yourself: the middle half (25th–75th
percentile) of the previous 28 days, not counting the day itself.
"""
import math
import statistics
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

Series = Dict[date, float]

BASELINE_DAYS = 28
MIN_BASELINE = 10
MIN_GROUP_DAYS = 8
FDR = 0.05


def series(rows: Iterable[Dict[str, Any]], column: str, key: str = "date") -> Series:
    return {row[key]: float(row[column]) for row in rows if row.get(column) is not None}


def typical(values: Series, day: date, window: int = BASELINE_DAYS,
            minimum: int = MIN_BASELINE) -> Optional[Dict[str, float]]:
    past = [values[day - timedelta(days=k)] for k in range(1, window + 1) if day - timedelta(days=k) in values]
    if len(past) < minimum:
        return None
    q1, median, q3 = statistics.quantiles(past, n=4, method="inclusive")
    return {"median": median, "q1": q1, "q3": q3, "days": len(past)}


def classify(value: Optional[float], band: Optional[Dict[str, float]]) -> Optional[str]:
    """high / low / normal against the band, None when either side is unknown."""
    if value is None or band is None:
        return None
    if value > band["q3"]:
        return "high"
    if value < band["q1"]:
        return "low"
    return "normal"


def tone(state: Optional[str], better: str) -> str:
    """good / bad / neutral. ``better`` is higher, lower or none."""
    if state in (None, "normal") or better == "none":
        return "neutral"
    return "good" if (state == "high") == (better == "higher") else "bad"


def window(values: Series, end: date, days: int) -> List[Dict[str, Any]]:
    """Daily points ending at ``end``; missing days stay null so charts can break the line."""
    return [{"date": (end - timedelta(days=k)).isoformat(), "value": values.get(end - timedelta(days=k))}
            for k in range(days - 1, -1, -1)]


def compare(yes: List[float], no: List[float]) -> Dict[str, Any]:
    """Difference of means with a normal-approximation 95% interval (Welch standard error)."""
    if len(yes) < MIN_GROUP_DAYS or len(no) < MIN_GROUP_DAYS:
        return {"status": "too_few"}
    diff = statistics.fmean(yes) - statistics.fmean(no)
    se = math.sqrt(statistics.variance(yes) / len(yes) + statistics.variance(no) / len(no))
    if se == 0:
        return {"status": "too_few"}
    p = 2 * (1 - statistics.NormalDist().cdf(abs(diff / se)))
    return {"status": "ok", "diff": diff, "low": diff - 1.96 * se, "high": diff + 1.96 * se, "p": p}


def benjamini_hochberg(pvalues: List[float]) -> List[float]:
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [1.0] * len(pvalues)
    running = 1.0
    for rank, index in reversed(list(enumerate(order, start=1))):
        running = min(running, pvalues[index] * len(pvalues) / rank)
        adjusted[index] = running
    return adjusted


def minutes_since_noon(value) -> float:
    """Clock time as minutes after the previous noon, so 23:30 < 01:10 compares the way nights do."""
    minutes = value.hour * 60 + value.minute
    return minutes - 720 if minutes >= 720 else minutes + 720


def clock_from_noon(minutes: float) -> str:
    total = int(round(minutes + 720)) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def minutes_of_day(value) -> float:
    """Clock time as minutes after midnight. Wake times use this: a wake at 12:35 is late morning, not past midnight."""
    return value.hour * 60 + value.minute


def clock_from_midnight(minutes: float) -> str:
    total = int(round(minutes)) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"
