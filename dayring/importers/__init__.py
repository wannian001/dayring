"""Importers turn exports from other apps into the CSV tables in ``dayring/schema.py``.

Each importer reads one kind of source and writes one table with ``store.write_table``,
merging with what is already in the data directory (see each module for its merge rule).
``dayring.importers.cli`` wires them into ``dayring import ...``.
"""
from typing import Dict, Tuple

# command name -> (module, table it writes, one-line description)
IMPORTERS: Dict[str, Tuple[str, str, str]] = {
    "apple-health": ("dayring.importers.apple_health", "body_daily",
                     "Apple Health export.zip / export.xml -> body_daily"),
    "ics": ("dayring.importers.ics", "events", "iCalendar .ics file -> events"),
    "macos-screentime": ("dayring.importers.macos_screentime", "screen_sessions",
                         "macOS Screen Time (Biome App.InFocus, experimental) -> screen_sessions"),
    "csv": ("dayring.importers.csv_map", "any", "any CSV with your own column names -> any table"),
}
