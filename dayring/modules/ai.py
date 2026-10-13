"""AI work: how much AI agents worked for you, on what instructions, next to your own focused work.

From ai_work and ai_prompts (dayring import ai-logs: Claude Code and Codex logs, times and counts only).
AI work is the minutes an agent was working in sessions you started (scheduled tasks and scripts are
shown on their own, never in your numbers). Instructions are the prompts you typed. Your focused work
is the Time page's focus minutes (work and learning apps, each minute counted once across devices).

The page shows the same 7 whole days as the Time page would (the latest days with a whole AI record,
stepping 7 at a time) and compares each number with your normal the same way: the middle half of your
7-day averages in the 28 days before the first day (time.typical_week). The two ratios, AI minutes per
instruction and AI work over your focused work, are worked out from 7-day totals, never as a mean of
daily ratios, and so is their normal. A day before the first AI record, or the cut-off last import day,
is unknown, never zero; a day in between without any AI use is a real zero.

Usage is input, not output: an agent going round in circles also adds minutes. So the AI numbers are
never coloured better or worse; only your own focused work keeps the Time page's direction. What came
out is the deadlines marked submitted or done, per 7 days, next to the focused work and AI work it took.
"""
import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .. import stats
from ..context import SCREEN_PARTS, Context, iso
from . import time as time_page

SPAN = 7
HISTORY = 30
WEEKS = 8
KEYS = ("ai", "prompts", "per_prompt", "focus", "leverage")
BETTER = {"ai": "none", "prompts": "none", "per_prompt": "none", "focus": "higher", "leverage": "none"}
RATIOS = {"per_prompt": ("ai", "prompts", 1.0), "leverage": ("ai", "focus", 100.0)}  # numerator, denominator, scale
MIN_WIDTH = {"ai": 15.0, "prompts": 2.0, "per_prompt": 1.0, "focus": time_page.SPAN_MIN_WIDTH, "leverage": 10.0}
DONE = ("submitted", "done")


def _daily(ctx: Context) -> Dict[date, Dict[str, Optional[float]]]:
    """Per whole day: your AI minutes and instructions (None before the AI record or on the cut-off day),
    scheduled and script minutes, and your focused minutes (None without a whole screen record)."""
    ai = ctx.ai_known_days()
    time = ctx.time_days()
    days = set(ai) | {d for d, td in time.items() if d < ctx.today and td.admitted}
    out = {}
    for d in days:
        ad, td = ai.get(d), time.get(d)
        focus = td.totals()["focus"] if td is not None else None
        out[d] = {"ai": ad.you if ad else None, "prompts": ad.prompts if ad else None,
                  "other": ad.other if ad else None, "focus": focus}
    return out


def _series(daily: Dict[date, Dict[str, Optional[float]]], key: str) -> stats.Series:
    return {d: v[key] for d, v in daily.items() if v[key] is not None}


def typical_ratio(num: stats.Series, den: stats.Series, first: date, scale: float) -> Optional[Dict[str, float]]:
    """Your normal for a 7-day ratio: the middle half of the ratios of the 7-day totals ending on each of the
    28 days before ``first`` (days with both values, at least time.WEEK_MIN_DAYS of the 7)."""
    ratios = []
    for k in range(1, stats.BASELINE_DAYS + 1):
        end = first - timedelta(days=k)
        both = [end - timedelta(days=j) for j in range(SPAN) if end - timedelta(days=j) in num and end - timedelta(days=j) in den]
        bottom = sum(den[d] for d in both)
        if len(both) >= time_page.WEEK_MIN_DAYS and bottom > 0:
            ratios.append(sum(num[d] for d in both) / bottom * scale)
    if len(ratios) < stats.MIN_BASELINE:
        return None
    q1, median, q3 = statistics.quantiles(ratios, n=4, method="inclusive")
    return {"median": median, "q1": q1, "q3": q3, "days": len(ratios)}


def _compare(key: str, value: Optional[float], band: Optional[Dict[str, float]]) -> Dict[str, Any]:
    """Like the Time page: a change counts when it lies one band width outside your normal."""
    state = stats.classify(value, band)
    share = 0.0 if key in RATIOS else time_page.MIN_WIDTH_SHARE
    score = time_page.score(value, band, MIN_WIDTH[key], share)
    return {"key": key, "value": value, "band": band, "state": state,
            "delta": value - band["median"] if state is not None else None,
            "score": score, "clear": score >= time_page.STANDOUT_MIN, "tone": stats.tone(state, BETTER[key])}


def _span(days: List[date], daily) -> Dict[str, Any]:
    rows = [daily.get(d) or {"ai": None, "prompts": None, "other": None, "focus": None} for d in days]
    known = {k: sum(1 for r in rows if r[k] is not None) for k in ("ai", "prompts", "other", "focus")}
    avg = {k: (sum(r[k] for r in rows if r[k] is not None) / known[k] if known[k] else None) for k in known}
    for key, (top, bottom, scale) in RATIOS.items():
        both = [r for r in rows if r[top] is not None and r[bottom] is not None]
        below = sum(r[bottom] for r in both)
        avg[key] = sum(r[top] for r in both) / below * scale if below > 0 else None
        known[key] = len(both)
    return {"avg": avg, "known": known}


def _hours(ctx: Context, days: List[date]) -> List[Dict[str, Optional[float]]]:
    """The average hour of the shown days: sleep and screens from the Time page, AI work and instructions."""
    base = time_page._average(days, ctx)["by_hour"]
    ai = ctx.ai_known_days()
    have = [ai[d] for d in days if d in ai]
    out = []
    for h in range(24):
        slot = {k: base[h].get(k) for k in ("sleep",) + SCREEN_PARTS}
        for k in ("you", "other", "prompts"):
            slot[k] = sum(ad.by_hour[h].get(k, 0.0) for ad in have) / len(have) if have else None
        out.append(slot)
    return out


def _weeks(ctx: Context, daily, end: date) -> List[Dict[str, Any]]:
    """Eight blocks of 7 days ending on ``end``: AI work and focused work a day, and the deadlines marked
    submitted or done in each (by due date), with the hours of each it took."""
    done = [r for r in ctx.store.rows("deadlines") if r.get("status") in DONE]
    out = []
    for k in range(WEEKS - 1, -1, -1):
        last = end - timedelta(days=SPAN * k)
        first = last - timedelta(days=SPAN - 1)
        block = [first + timedelta(days=j) for j in range(SPAN)]
        s = _span(block, daily)
        n = sum(1 for r in done if first <= r["due"].date() <= last)
        focus_total = s["avg"]["focus"] * s["known"]["focus"] if s["avg"]["focus"] is not None else None
        ai_total = s["avg"]["ai"] * s["known"]["ai"] if s["avg"]["ai"] is not None else None
        out.append({"from": iso(first), "to": iso(last), "ai": s["avg"]["ai"], "focus": s["avg"]["focus"],
                    "ai_known": s["known"]["ai"], "focus_known": s["known"]["focus"], "done": n,
                    "focus_per_done": focus_total / n if n and focus_total is not None and s["known"]["focus"] * 2 >= SPAN else None,
                    "ai_per_done": ai_total / n if n and ai_total is not None and s["known"]["ai"] * 2 >= SPAN else None})
    return out


def data_days(ctx: Context) -> List[date]:
    """Every whole day with an AI record, oldest first."""
    return sorted(ctx.ai_known_days())


def build(ctx: Context, day: Optional[str] = None) -> Dict[str, Any]:
    every = data_days(ctx)
    newest = every[-1] if every else None
    base = {"page": "ai", "today": iso(ctx.today), "now": iso(ctx.now), "newest": iso(newest)}
    end = date.fromisoformat(day) if day else ctx.today - timedelta(days=1)
    recent = [d for d in every if d <= end][-SPAN:]
    if not recent:
        return {**base, "day": iso(end), "empty": True, "next": iso(every[min(SPAN, len(every)) - 1]) if every else None}
    daily = _daily(ctx)
    last = recent[-1]
    span = _span(recent, daily)
    metrics = {}
    for key in KEYS:
        enough = span["known"][key] * 2 >= len(recent)
        band = None
        if enough:
            if key in RATIOS:
                top, bottom, scale = RATIOS[key]
                band = typical_ratio(_series(daily, top), _series(daily, bottom), recent[0], scale)
            else:
                band = time_page.typical_week(_series(daily, key), recent[0])
        m = _compare(key, span["avg"][key], band)
        m.update(known=span["known"][key], few=not enough)
        metrics[key] = m
    changes = sorted((m for m in metrics.values() if m["clear"]), key=lambda m: -m["score"])
    history = []
    for k in range(HISTORY - 1, -1, -1):
        d = last - timedelta(days=k)
        row = daily.get(d) or {"ai": None, "prompts": None, "other": None, "focus": None}
        history.append({"date": iso(d), **row, "in_span": d in recent})
    before = [d for d in every if d < recent[0]]
    later = [d for d in every if d > last]
    return {**base, "day": iso(last), "empty": False,
            "span": {"from": iso(recent[0]), "to": iso(last), "n": len(recent), "avg": span["avg"], "known": span["known"],
                     "metrics": metrics, "changes": changes, "by_hour": _hours(ctx, recent),
                     "days": [{"date": iso(d), **(daily.get(d) or {})} for d in recent]},
            "history": history, "weeks": _weeks(ctx, daily, last),
            "baseline_days": stats.BASELINE_DAYS, "baseline_min": stats.MIN_BASELINE,
            "prev": iso(before[-1]) if before else None,
            "next": iso(later[min(SPAN, len(later)) - 1]) if later else None}


def static_params(ctx: Context, steps: int = 3) -> List[Optional[str]]:
    """The latest page, the newest day and a few pages back along "Earlier", as the Time page does."""
    params: List[Optional[str]] = [None]
    page = build(ctx)
    if page.get("newest"):
        params.append(page["newest"])
    for _ in range(steps):
        if page.get("empty") or not page.get("prev"):
            break
        params.append(page["prev"])
        page = build(ctx, page["prev"])
    return params
