"""Read the CSV tables in the data directory, checked against ``schema.TABLES``.

A bad cell never stops the page: the row is skipped and the problem is kept so
the Data page can show which file, line and column to fix.
"""
import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import TABLES, Table


@dataclass
class Problem:
    table: str
    line: int
    column: str
    message: str

    def as_dict(self) -> Dict[str, Any]:
        return {"table": self.table, "line": self.line, "column": self.column, "message": self.message}


@dataclass
class Loaded:
    table: Table
    rows: List[Dict[str, Any]] = field(default_factory=list)
    problems: List[Problem] = field(default_factory=list)
    present: bool = False
    modified: Optional[datetime] = None


class Store:
    """All tables, loaded once per request. Rows are plain dicts keyed by column name."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, Loaded] = {}

    def load(self, name: str) -> Loaded:
        if name in self._cache:
            return self._cache[name]
        table = TABLES[name]
        result = Loaded(table=table)
        path = self.data_dir / table.filename
        if path.is_file():
            result.present = True
            result.modified = datetime.fromtimestamp(path.stat().st_mtime)
            seen: Dict[tuple, int] = {}
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                header = reader.fieldnames or []
                missing = [c.name for c in table.columns if c.required and c.name not in header]
                if missing:
                    result.problems.append(Problem(name, 1, ",".join(missing), "required column missing"))
                else:
                    for line, raw in enumerate(reader, start=2):
                        row: Dict[str, Any] = {}
                        bad = False
                        for col in table.columns:
                            try:
                                row[col.name] = col.parse(raw.get(col.name))
                            except (ValueError, TypeError) as error:
                                result.problems.append(Problem(name, line, col.name, str(error)))
                                bad = True
                                break
                        if bad:
                            continue
                        problem = table.interval_problem(row)
                        if problem:
                            result.problems.append(Problem(name, line, table.interval[1], problem))
                            continue
                        key = tuple(row[k] for k in table.key)
                        if key in seen:  # later rows win, like a revision
                            result.rows[seen[key]] = row
                            continue
                        seen[key] = len(result.rows)
                        result.rows.append(row)
        self._cache[name] = result
        return result

    def rows(self, name: str) -> List[Dict[str, Any]]:
        return self.load(name).rows

    def by_date(self, name: str, key: str = "date") -> Dict[date, Dict[str, Any]]:
        return {row[key]: row for row in self.rows(name)}

    def problems(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name in TABLES:
            out += [p.as_dict() for p in self.load(name).problems]
        return out


def write_table(data_dir: Path, name: str, rows: List[Dict[str, Any]]) -> Path:
    """Write rows in schema column order. Used by importers and the demo generator."""
    table = TABLES[name]
    path = Path(data_dir) / table.filename
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([c.name for c in table.columns])
        for row in rows:
            writer.writerow([_cell(row.get(c.name)) for c in table.columns])
    tmp.replace(path)
    return path


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)
