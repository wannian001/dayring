"""Soreness check-ins: where you were sore in the morning and how much, in soreness.csv (see schema.py).

The Recovery page writes a check-in when you tap regions on the body figure and save; `healthaio soreness set` does
the same from the command line (for a script or an assistant). A check-in replaces that morning's rows and leaves
every other day as it was. Saving with nothing tapped writes one row, region `none`, so "checked, nothing sore" and
"not checked" stay apart. Rows that do not parse (a hand-edited file) are never rewritten away: the table is read
row by row, and only that morning's rows are replaced.
"""
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from . import state
from .schema import SORE_REGIONS, TABLES
from .store import write_table

LEVELS = (1, 2, 3)  # a little, clearly sore, very sore


class SorenessError(ValueError):
    """A check-in that cannot be written: an unknown region, a level out of range, a date in the future."""


def check(levels: Any) -> Dict[str, int]:
    """The check-in as {region: level} with only sore regions, after validating everything."""
    if not isinstance(levels, dict):
        raise SorenessError("levels must be an object of region: level")
    out: Dict[str, int] = {}
    for region, level in levels.items():
        if region not in SORE_REGIONS:
            raise SorenessError(f"unknown region {region!r}; one of {', '.join(SORE_REGIONS)}")
        if level in (0, None):
            continue
        if isinstance(level, bool) or level not in LEVELS:
            raise SorenessError(f"{region}: level must be 0 to 3")
        out[region] = int(level)
    return out


def parse_day(text: Any, today: date) -> date:
    try:
        day = date.fromisoformat(str(text))
    except ValueError:
        raise SorenessError("date must be YYYY-MM-DD") from None
    if day > today:
        raise SorenessError("a check-in cannot be for a day that has not come")
    return day


def save(cfg, day: date, levels: Dict[str, int]) -> Dict[str, Any]:
    """Replace ``day``'s rows in soreness.csv with this check-in, holding the write lock the importers hold."""
    path = Path(cfg.data_dir) / TABLES["soreness"].filename
    with state.write_lock(cfg):
        kept = []
        if path.is_file():
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for raw in csv.DictReader(handle):
                    if (raw.get("date") or "").strip() != day.isoformat():
                        kept.append(raw)  # as written, even a row that does not parse
        new = [{"date": day, "region": region, "level": level} for region, level in sorted(levels.items())]
        if not new:
            new = [{"date": day, "region": "none", "level": 0}]
        rows = sorted(kept + [{k: _text(v) for k, v in r.items()} for r in new], key=lambda r: (r.get("date") or "", r.get("region") or ""))
        write_table(cfg.data_dir, "soreness", rows)
    return {"ok": True, "date": day.isoformat(), "levels": levels}


def _text(value: Any) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def from_browser(cfg, request: Any, now: Optional[datetime] = None) -> Dict[str, Any]:
    """A check-in sent by the Recovery page: {"date": "YYYY-MM-DD", "levels": {"torso": 2, ...}}."""
    if not isinstance(request, dict):
        raise SorenessError("expected a JSON object")
    today = (now or datetime.now()).date()
    day = parse_day(request.get("date"), today)
    return save(cfg, day, check(request.get("levels")))


def run(args: Any, cfg) -> int:
    """`healthaio soreness set [--date D] REGION=LEVEL ...` (no pairs: checked, nothing sore)."""
    try:
        today = datetime.now(cfg.tz).date() if getattr(cfg, "tz", None) else date.today()
        day = parse_day(args.date or today.isoformat(), today)
        levels: Dict[str, Any] = {}
        for pair in args.levels:
            region, _, level = pair.partition("=")
            try:
                levels[region] = int(level)
            except ValueError:
                raise SorenessError(f"{pair!r}: expected REGION=LEVEL, e.g. left_calf=2") from None
        result = save(cfg, day, check(levels))
    except SorenessError as error:
        print(f"healthaio soreness: {error}")
        return 2
    sore = ", ".join(f"{r} {lv}" for r, lv in result["levels"].items()) or "nothing sore"
    print(f"{result['date']}: {sore}")
    return 0
