"""Any CSV with its own column names -> any Health AIO table.

``--map 'Date=date,Weight (kg)=weight_kg'`` renames source columns to schema columns. A source
column whose name already equals a schema column (ignoring case) is taken as is, so only the
differing names need mapping. Every cell is checked with the schema's ``Column.parse``; a row
with a bad cell is skipped and reported with its line number, the rest are imported.

Dates in another layout can be read with ``--date-format`` / ``--datetime-format`` (``strptime``
codes, e.g. ``%d/%m/%Y``); ISO values are accepted either way. The delimiter (comma, semicolon,
tab, pipe) is detected unless given. For ``screen_sessions`` without a category column, the
category comes from ``screen_categories.json`` by app name or domain.

Merge rule: imported rows replace existing rows with the same key (the table's key columns, e.g.
``date`` for ``body_daily``), other existing rows are kept; ``replace=True`` rewrites the table
with only the imported rows. Within the file, a later row with the same key wins.
"""
import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..schema import TABLES
from ..store import write_table
from ._common import Row, Summary, merge_write, span

PAIR = re.compile(r"\s*(.+?)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,|$)")


class MappingError(ValueError):
    pass


def parse_mapping(texts: List[str]) -> Dict[str, str]:
    """['Date=date,Weight (kg)=weight_kg'] -> {'Date': 'date', 'Weight (kg)': 'weight_kg'}.
    Source names may contain commas; target names are schema column names."""
    mapping: Dict[str, str] = {}
    for text in texts:
        position = 0
        text = text.strip()
        while position < len(text):
            match = PAIR.match(text, position)
            if not match or match.end() == position:
                raise MappingError(f"cannot read mapping near {text[position:]!r}; use 'Source=column,...'")
            mapping[match.group(1)] = match.group(2)
            position = match.end()
    return mapping


def _dialect(sample: str, delimiter: Optional[str]):
    if delimiter:
        return delimiter
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def import_csv(name: str, path: Path, cfg, mapping_texts: Optional[List[str]] = None,
               date_format: Optional[str] = None, datetime_format: Optional[str] = None,
               delimiter: Optional[str] = None, replace: bool = False) -> Summary:
    if name not in TABLES:
        raise MappingError(f"unknown table {name!r}; choose one of {', '.join(TABLES)}")
    table = TABLES[name]
    columns = {c.name: c for c in table.columns}
    mapping = parse_mapping(mapping_texts or [])
    summary = Summary(table=name, source=str(path))

    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=_dialect(text[:4096], delimiter))
    header = [h for h in (reader.fieldnames or []) if h is not None]
    for source, target in mapping.items():
        if target not in columns:
            raise MappingError(f"{target!r} is not a column of {name}; columns: {', '.join(columns)}")
        if source not in header:
            raise MappingError(f"{source!r} is not a column in {path}; the file has: {', '.join(header)}")
    targets: Dict[str, str] = {}  # schema column -> source column
    for source, target in mapping.items():
        targets[target] = source
    for source in header:
        lowered = source.strip().lower()
        if lowered in columns and lowered not in targets and source not in mapping:
            targets[lowered] = source

    categorizer = None
    if name == "screen_sessions" and "category" not in targets:
        from .macos_screentime import Categorizer  # only needed for this case
        categorizer = Categorizer.load(cfg.data_dir)
        summary.notes.append("category filled in from screen_categories.json")
    missing = [c.name for c in table.columns if c.required and c.name not in targets
               and not (categorizer is not None and c.name == "category")]
    if missing:
        raise MappingError(f"no source column for required {', '.join(missing)}; add them to --map")
    unused = [h for h in header if h not in targets.values()]
    if unused:
        summary.notes.append(f"ignored columns: {', '.join(unused)}")

    rows: Dict[tuple, Row] = {}
    repeated = 0
    for raw in reader:
        line = reader.line_num
        row: Row = {}
        bad = False
        for target, source in targets.items():
            col = columns[target]
            cell = (raw.get(source) or "").strip()
            try:
                if cell and col.type == "date" and date_format:
                    cell = _reformat(cell, date_format, "date")
                elif cell and col.type == "datetime" and datetime_format:
                    cell = _reformat(cell, datetime_format, "datetime")
                row[target] = col.parse(cell)
            except (ValueError, TypeError) as error:
                summary.problems.append(f"line {line}: {source!r} -> {target}: {cell!r}: {error}")
                bad = True
                break
        if bad:
            continue
        if categorizer is not None:
            row["category"] = categorizer.category(row["app"])
        key = tuple(row.get(k) for k in table.key)
        if key in rows:
            repeated += 1
        rows[key] = row
    if repeated:
        summary.notes.append(f"{repeated} row(s) repeated a key earlier in the file; the later row was kept")

    imported = [rows[k] for k in sorted(rows)]
    if replace:
        target_path = write_table(Path(cfg.data_dir), name, imported)
        total, notes = len(imported), []
    else:
        target_path, total, notes = merge_write(cfg.data_dir, name, imported)
    summary.imported, summary.total, summary.path = len(imported), total, target_path
    summary.first, summary.last = span(imported, table.key[0])
    summary.notes += notes
    return summary


def _reformat(cell: str, fmt: str, kind: str) -> str:
    try:
        datetime.fromisoformat(cell)
        return cell  # already ISO
    except ValueError:
        pass
    parsed = datetime.strptime(cell, fmt)
    return parsed.date().isoformat() if kind == "date" else parsed.strftime("%Y-%m-%dT%H:%M:%S")
