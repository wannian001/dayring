"""``healthaio collect``: the importers that can run by themselves, and ``healthaio status`` for the Mac app.

The Mac app runs ``collect`` every few hours. Screen Time keeps only about four weeks, so a gap of more than that is
lost for good; the app holds Full Disk Access so that its child processes (this one) may read it. Which importers run
is ``[collect] sources`` in healthaio.toml (default: Screen Time only; add "ai-logs" for Claude Code and Codex).
"""
import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, capture, config as config_mod, iphone, phone, state, update
from .schema import TABLES

LATEST = {"body_daily": "date", "workouts": "start", "meals": "time", "screen_sessions": "start", "events": "start",
          "ai_work": "start"}


def full_disk_access() -> Optional[bool]:
    """Whether this process may read the Screen Time folder; None when this is not a Mac or it has no such folder."""
    if sys.platform != "darwin":
        return None
    from .importers.macos_screentime import DEFAULT_ROOT, STREAM
    folder = DEFAULT_ROOT / STREAM
    try:
        os.listdir(folder)
        return True
    except PermissionError:
        return False
    except OSError:
        return None


def collect(cfg) -> Dict[str, Any]:
    from .importers.ai_logs import import_ai_logs
    from .importers.macos_screentime import import_screentime
    runs = {"macos-screentime": lambda: import_screentime(cfg), "ai-logs": lambda: import_ai_logs(cfg)}
    sources: List[Dict[str, Any]] = []
    for name in cfg.collect_sources:
        if name == "macos-screentime" and sys.platform != "darwin":
            sources.append({"name": name, "ok": False, "message": "Screen Time can only be read on a Mac"})
            continue
        try:
            with state.write_lock(cfg):
                summary = runs[name]()
            sources.append({"name": name, "ok": True, "message": "\n".join(summary.lines(max_problems=5))})
        except Exception as error:  # one source failing must not stop the others
            sources.append({"name": name, "ok": False, "message": str(error) or type(error).__name__})
    result = {"ok": all(s["ok"] for s in sources), "at": state.now_iso(), "sources": sources}
    state.write_json(state.folder(cfg) / "collect.json", result)
    return result


def latest(cfg) -> Dict[str, Optional[str]]:
    """The newest date or time in each table (ISO text sorts in time order)."""
    out: Dict[str, Optional[str]] = {}
    for name, column in LATEST.items():
        path = Path(cfg.data_dir) / TABLES[name].filename
        best = None
        if path.is_file():
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    value = (row.get(column) or "").strip()
                    if value and (best is None or value > best):
                        best = value
        out[name] = best
    return out


def status(cfg, port: int = 8790) -> Dict[str, Any]:
    path = config_mod.find_config(Path(cfg.root))
    return {"version": __version__, "config": str(path) if path else None, "data_dir": str(cfg.data_dir),
            "timezone": cfg.timezone, "port": port,
            "collect": state.read_json(state.folder(cfg) / "collect.json"),
            "devices": phone.devices(cfg), "latest": latest(cfg), "last_package": capture.last_receipt(cfg),
            "full_disk_access": full_disk_access(), "iphone": iphone.status(cfg), "update": update.cached(cfg)}
