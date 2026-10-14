"""The morning check-in on the Recovery page: how you feel (2, 5 or 8) and where you are sore (see schema.py).

One check-in writes two tables: the feeling goes into that morning's row of self_report.csv (`feel`; energy, focus and
the note on that row stay as they were), the soreness replaces that morning's rows in soreness.csv. Saving with no
region tapped writes one soreness row, region `none`, so "checked, nothing sore" and "not checked" stay apart; saving
without a feeling leaves `feel` as it was. Rows of other days are never touched, and rows that do not parse (a
hand-edited file) are kept as written. `healthaio checkin` does the same from the command line (for a script or an
assistant).
"""
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import state
from .schema import FEELINGS, SORE_REGIONS, TABLES
from .store import write_table

LEVELS = (1, 2, 3)  # a little, clearly sore, very sore


class CheckinError(ValueError):
    """A check-in that cannot be written: an unknown region, a level or feeling out of range, a day not yet come."""


def check(levels: Any) -> Dict[str, int]:
    """The soreness as {region: level} with only sore regions, after validating everything."""
    if not isinstance(levels, dict):
        raise CheckinError("levels must be an object of region: level")
    out: Dict[str, int] = {}
    for region, level in levels.items():
        if region not in SORE_REGIONS:
            raise CheckinError(f"unknown region {region!r}; one of {', '.join(SORE_REGIONS)}")
        if level in (0, None):
            continue
        if isinstance(level, bool) or level not in LEVELS:
            raise CheckinError(f"{region}: level must be 0 to 3")
        out[region] = int(level)
    return out


def check_feel(feel: Any) -> Optional[int]:
    if feel is None:
        return None
    if isinstance(feel, bool) or feel not in FEELINGS:
        raise CheckinError(f"feel must be one of {', '.join(map(str, FEELINGS))}")
    return int(feel)


def parse_day(text: Any, today: date) -> date:
    try:
        day = date.fromisoformat(str(text))
    except ValueError:
        raise CheckinError("date must be YYYY-MM-DD") from None
    if day > today:
        raise CheckinError("a check-in cannot be for a day that has not come")
    return day


def _rows(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def save(cfg, day: date, levels: Dict[str, int], feel: Optional[int] = None) -> Dict[str, Any]:
    """Write this check-in, holding the write lock the importers hold."""
    stamp = day.isoformat()
    with state.write_lock(cfg):
        sore = [r for r in _rows(Path(cfg.data_dir) / TABLES["soreness"].filename) if (r.get("date") or "").strip() != stamp]
        new = [{"date": stamp, "region": region, "level": str(level)} for region, level in sorted(levels.items())]
        sore += new or [{"date": stamp, "region": "none", "level": "0"}]
        write_table(cfg.data_dir, "soreness", sorted(sore, key=lambda r: (r.get("date") or "", r.get("region") or "")))
        if feel is not None:
            rows = _rows(Path(cfg.data_dir) / TABLES["self_report"].filename)
            mine = next((r for r in rows if (r.get("date") or "").strip() == stamp), None)
            if mine is None:
                rows.append({"date": stamp, "feel": str(feel)})
            else:
                mine["feel"] = str(feel)
            write_table(cfg.data_dir, "self_report", sorted(rows, key=lambda r: r.get("date") or ""))
    return {"ok": True, "date": stamp, "levels": levels, "feel": feel}


def from_browser(cfg, request: Any, now: Optional[datetime] = None) -> Dict[str, Any]:
    """A check-in sent by the Recovery page: {"date": "YYYY-MM-DD", "levels": {"torso": 2, ...}, "feel": 5}."""
    if not isinstance(request, dict):
        raise CheckinError("expected a JSON object")
    today = (now or datetime.now()).date()
    day = parse_day(request.get("date"), today)
    return save(cfg, day, check(request.get("levels", {})), check_feel(request.get("feel")))


def run(args: Any, cfg) -> int:
    """`healthaio checkin [--date D] [--feel 2|5|8] REGION=LEVEL ...` (no pairs: nothing sore)."""
    try:
        today = datetime.now(cfg.tz).date() if getattr(cfg, "tz", None) else date.today()
        day = parse_day(args.date or today.isoformat(), today)
        levels: Dict[str, Any] = {}
        for pair in args.levels:
            region, _, level = pair.partition("=")
            try:
                levels[region] = int(level)
            except ValueError:
                raise CheckinError(f"{pair!r}: expected REGION=LEVEL, e.g. left_calf=2") from None
        result = save(cfg, day, check(levels), check_feel(args.feel))
    except CheckinError as error:
        print(f"healthaio checkin: {error}")
        return 2
    sore = ", ".join(f"{r} {lv}" for r, lv in result["levels"].items()) or "nothing sore"
    feel = f", feeling {result['feel']}" if result["feel"] is not None else ""
    print(f"{result['date']}: {sore}{feel}")
    return 0
