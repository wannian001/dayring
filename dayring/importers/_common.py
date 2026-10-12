"""Shared pieces for importers: validating rows against the schema and merging with an existing table."""
import csv
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..schema import TABLES, Table
from ..store import write_table

Row = Dict[str, Any]


@dataclass
class Summary:
    """What an import did, printed by the CLI and checked by tests."""
    table: str
    source: str = ""
    imported: int = 0          # rows this import produced
    total: int = 0             # rows in the table file after merging
    first: Any = None          # earliest date/datetime among imported rows
    last: Any = None
    path: Optional[Path] = None
    problems: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)  # importer-specific tallies, e.g. workouts

    def lines(self, max_problems: int = 15) -> List[str]:
        span = ""
        if self.first is not None:
            span = f", {_short(self.first)} to {_short(self.last)}"
        out = [f"{self.table}: {self.imported} rows imported{span}; "
               f"{self.total} rows now in {self.path or self.table + '.csv'}"]
        out += [f"  note: {n}" for n in self.notes]
        if self.problems:
            out.append(f"  {len(self.problems)} problem(s):")
            out += [f"    {p}" for p in self.problems[:max_problems]]
            if len(self.problems) > max_problems:
                out.append(f"    ... and {len(self.problems) - max_problems} more")
        return out


def _short(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def format_cell(value: Any) -> str:
    """Same text ``store.write_table`` writes, so validation sees what the store will read back."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "nan"
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def validate(table: Table, row: Row, where: str, problems: List[str]) -> Optional[Row]:
    """Check every cell with ``Column.parse``. A bad optional cell becomes empty (unknown);
    a bad required cell drops the row. Problems are appended as readable text."""
    out: Row = {}
    for col in table.columns:
        value = row.get(col.name)
        try:
            col.parse(format_cell(value))
        except (ValueError, TypeError) as error:
            problems.append(f"{where}: {col.name}={format_cell(value)!r}: {error}")
            if col.required:
                return None
            value = None
        out[col.name] = value
    problem = table.interval_problem(out)
    if problem:
        problems.append(f"{where}: {problem}")
        return None
    return out


def read_raw(path: Path) -> List[Tuple[int, Dict[str, str]]]:
    """Existing rows as raw text with their line numbers; nothing is dropped."""
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [(line, {k: (v or "") for k, v in raw.items() if k is not None})
                for line, raw in enumerate(reader, start=2)]


def merge_write(data_dir: Path, name: str, new_rows: List[Row],
                drop: Optional[Callable[[Dict[str, Any], Dict[str, str]], bool]] = None,
                combine: Optional[Callable[[Dict[str, str], Row], Row]] = None) -> Tuple[Path, int, List[str]]:
    """Merge ``new_rows`` into the table file and write it in key order.

    - Existing rows are kept unless ``drop(parsed_key_columns, raw_row)`` says so.
    - A new row with the same key as a kept row replaces it, or ``combine(old_raw, new)`` decides.
    - Existing rows whose key cells do not parse are kept untouched at the end, so nothing the
      user typed is lost; they are reported so the Data page and the summary can point at them.
    Returns (path, rows written, notes).
    """
    table = TABLES[name]
    path = Path(data_dir) / table.filename
    keyed: Dict[tuple, Row] = {}
    broken: List[Row] = []
    notes: List[str] = []
    for line, raw in read_raw(path):
        try:
            key_values = {k: table.column(k).parse(raw.get(k)) for k in table.key}
        except (ValueError, TypeError):
            broken.append(raw)
            notes.append(f"kept existing line {line} of {table.filename} as is (its key does not parse)")
            continue
        if drop is not None and drop(key_values, raw):
            continue
        keyed[tuple(key_values[k] for k in table.key)] = raw
    for row in new_rows:
        key = tuple(row[k] for k in table.key)
        if key in keyed and combine is not None:
            keyed[key] = combine(keyed[key], row)
        else:
            keyed[key] = row
    rows = [keyed[k] for k in sorted(keyed)] + broken
    write_table(Path(data_dir), name, rows)
    return path, len(rows), notes


def span(rows: List[Row], column: str) -> Tuple[Any, Any]:
    values = [r[column] for r in rows if r.get(column) is not None]
    return (min(values), max(values)) if values else (None, None)
