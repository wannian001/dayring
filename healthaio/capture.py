"""Packages from the iPhone app: check, store once, write into the tables. The contract is docs/CAPTURE.md.

A package carries Apple Health samples with the attribute names of Apple's ``export.xml``. The server turns it back
into that XML and reads it with ``importers.apple_health``, so an export imported by hand and the same days sent by
the app give the same rows. Only the window the phone read is written: ``body_daily`` rows dated inside it, workouts
and meals that start inside it.
"""
import hashlib
import io
import json
import os
import re
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from . import state
from .importers import apple_health
from .importers._common import Row

SCHEMA = "healthaio-capture-v1"
KINDS = ("health",)
MAX_BYTES = 8 * 1024 * 1024
MAX_WINDOW_DAYS = 4
MAX_RECORDS = 300_000
MAX_WORKOUTS = 2_000
PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RECORD_FIELDS = ("type", "sourceName", "device", "unit", "startDate", "endDate", "value")
WORKOUT_FIELDS = ("workoutActivityType", "duration", "durationUnit", "sourceName", "device", "startDate", "endDate",
                  "totalEnergyBurned", "totalEnergyBurnedUnit")
METADATA = ("HKTimeZone", "HKFoodType", "HKFoodMeal", "meal")
STAT_FIELDS = ("type", "sum", "average", "unit")
TEXT_MAX = 200

_lock = threading.Lock()  # one package at a time: landing and projecting must not interleave


class CaptureError(ValueError):
    status = 400


class Conflict(CaptureError):
    status = 409


# ---------------------------------------------------------------- checking

def _text(value: Any, where: str, required: bool = True, limit: int = TEXT_MAX) -> Optional[str]:
    if value is None or value == "":
        if required:
            raise CaptureError(f"{where} is missing")
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise CaptureError(f"{where} must be text or a number")
    text = str(value)
    if len(text) > limit or any(ord(c) < 32 for c in text):
        raise CaptureError(f"{where} is too long or has control characters")
    return text


def _moment(value: Any, where: str) -> str:
    text = _text(value, where)
    if apple_health.parse_time(text) is None:
        raise CaptureError(f"{where} must look like 2026-10-13 07:12:00 +1100")
    return text


def _day(value: Any, where: str) -> date:
    try:
        return date.fromisoformat(_text(value, where))
    except ValueError:
        raise CaptureError(f"{where} must be YYYY-MM-DD") from None


def validate(package: Any) -> Dict[str, Any]:
    """The package with only the fields the server reads, or CaptureError saying what is wrong."""
    if not isinstance(package, dict):
        raise CaptureError("a package is a JSON object")
    if package.get("schema") != SCHEMA:
        raise CaptureError(f"schema must be {SCHEMA}")
    package_id = package.get("package_id")
    if not isinstance(package_id, str) or not PACKAGE_ID.match(package_id):
        raise CaptureError("package_id must be 1-128 letters, digits, dots, dashes or underscores")
    kind = package.get("kind")
    if kind not in KINDS:
        raise CaptureError(f"kind must be one of {', '.join(KINDS)}")
    device = package.get("device") if isinstance(package.get("device"), dict) else {}
    window = package.get("window")
    if not isinstance(window, dict):
        raise CaptureError("window is missing")
    start, end = _day(window.get("start_date"), "window.start_date"), _day(window.get("end_date"), "window.end_date")
    if end < start or (end - start).days >= MAX_WINDOW_DAYS:
        raise CaptureError(f"window must run forward and cover at most {MAX_WINDOW_DAYS} days")
    clean: Dict[str, Any] = {
        "schema": SCHEMA, "package_id": package_id, "kind": kind,
        "created_at": _text(package.get("created_at"), "created_at", required=False),
        "timezone": _text(package.get("timezone"), "timezone", required=False, limit=64),
        "device": {k: _text(device.get(k), f"device.{k}", required=False, limit=80) for k in ("id", "name", "app_version")},
        "window": {"start_date": start.isoformat(), "end_date": end.isoformat(),
                   "query_start": _moment(window.get("query_start"), "window.query_start"),
                   "query_end": _moment(window.get("query_end"), "window.query_end"),
                   "read_completed_at": _moment(window.get("read_completed_at"), "window.read_completed_at")},
    }
    records, workouts = package.get("records", []), package.get("workouts", [])
    if not isinstance(records, list) or not isinstance(workouts, list):
        raise CaptureError("records and workouts must be lists")
    if len(records) > MAX_RECORDS or len(workouts) > MAX_WORKOUTS:
        raise CaptureError("too many records for one package; send a shorter window")
    clean["records"] = [_record(r, f"records[{i}]") for i, r in enumerate(records)]
    clean["workouts"] = [_workout(w, f"workouts[{i}]") for i, w in enumerate(workouts)]
    return clean


def _record(record: Any, where: str) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise CaptureError(f"{where} must be an object")
    if record.get("type") not in apple_health.WANTED:
        raise CaptureError(f"{where}.type {record.get('type')!r} is not a type this app reads")
    out = {"type": record["type"]}
    for name in ("sourceName", "device", "unit", "value"):
        text = _text(record.get(name), f"{where}.{name}", required=name == "value")
        if text is not None:
            out[name] = text
    out["startDate"] = _moment(record.get("startDate"), f"{where}.startDate")
    out["endDate"] = _moment(record.get("endDate"), f"{where}.endDate")
    meta = record.get("metadata")
    if isinstance(meta, dict):
        kept = {k: _text(meta[k], f"{where}.metadata.{k}") for k in METADATA if meta.get(k) not in (None, "")}
        if kept:
            out["metadata"] = kept
    return out


def _workout(workout: Any, where: str) -> Dict[str, Any]:
    if not isinstance(workout, dict):
        raise CaptureError(f"{where} must be an object")
    out: Dict[str, Any] = {}
    for name in WORKOUT_FIELDS:
        if name in ("startDate", "endDate"):
            out[name] = _moment(workout.get(name), f"{where}.{name}")
        else:
            text = _text(workout.get(name), f"{where}.{name}", required=name == "workoutActivityType")
            if text is not None:
                out[name] = text
    events = workout.get("events", [])
    stats = workout.get("statistics", [])
    if not isinstance(events, list) or not isinstance(stats, list) or len(events) > 2000 or len(stats) > 50:
        raise CaptureError(f"{where}: events and statistics must be short lists")
    out["events"] = [{"type": _text(e.get("type"), f"{where}.events[{i}].type"),
                      "date": _moment(e.get("date"), f"{where}.events[{i}].date")}
                     for i, e in enumerate(events) if isinstance(e, dict)]
    out["statistics"] = [{k: _text(s.get(k), f"{where}.statistics[{i}].{k}", required=k == "type")
                          for k in STAT_FIELDS if s.get(k) not in (None, "") or k == "type"}
                         for i, s in enumerate(stats) if isinstance(s, dict)]
    return out


def canonical(package: Dict[str, Any]) -> bytes:
    return json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------- back to export.xml

def to_xml(package: Dict[str, Any]) -> bytes:
    """The package as the export.xml that Apple's Export All Health Data would have written for those samples."""
    root = ET.Element("HealthData", {"locale": "en_US"})
    ET.SubElement(root, "ExportDate", {"value": package["window"]["read_completed_at"]})
    for record in package["records"]:
        elem = ET.SubElement(root, "Record", {k: record[k] for k in RECORD_FIELDS if k in record})
        for key, value in (record.get("metadata") or {}).items():
            ET.SubElement(elem, "MetadataEntry", {"key": key, "value": value})
    for workout in package["workouts"]:
        elem = ET.SubElement(root, "Workout", {k: workout[k] for k in WORKOUT_FIELDS if k in workout})
        for event in workout["events"]:
            ET.SubElement(elem, "WorkoutEvent", {"type": event["type"], "date": event["date"]})
        for stat in workout["statistics"]:
            ET.SubElement(elem, "WorkoutStatistics", {k: v for k, v in stat.items() if v is not None})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------- storing and projecting

def _folder(cfg) -> Path:
    return state.folder(cfg) / "capture"


def _receipt_path(cfg, package_id: str) -> Path:
    return _folder(cfg) / "receipts" / f"{hashlib.sha256(package_id.encode()).hexdigest()}.json"


def _land(cfg, package_id: str, body: bytes) -> Path:
    """Create-only: temporary file, fsync, hard link to the final name. The final file is never rewritten."""
    day = datetime.now().date().isoformat()
    folder = _folder(cfg) / "landed" / day
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{package_id}.json"
    tmp = folder / f".{package_id}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, body)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.link(tmp, target)
    except FileExistsError:
        pass  # the same id landed the same day already; the receipt decides what it was
    finally:
        tmp.unlink(missing_ok=True)
    try:
        dir_fd = os.open(folder, os.O_RDONLY)
        os.fsync(dir_fd)
        os.close(dir_fd)
    except OSError:  # pragma: no cover - some file systems cannot fsync a folder
        pass
    return target


def receive(cfg, body: bytes, device: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
    """(HTTP status, receipt) for a package posted by a paired device."""
    if len(body) > MAX_BYTES:
        raise CaptureError(f"a package is at most {MAX_BYTES // (1024 * 1024)} MB; send a shorter window")
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CaptureError("the body is not JSON") from None
    package = validate(raw)
    stored = canonical(package)
    digest = hashlib.sha256(stored).hexdigest()
    with _lock:
        path = _receipt_path(cfg, package["package_id"])
        receipt = state.read_json(path)
        if receipt is not None:
            if receipt.get("sha256") != digest:
                raise Conflict("this package_id was already used for a different package")
            if receipt.get("status") != "projected":
                receipt = _project_and_record(cfg, package, receipt, path)
            return 200, receipt
        landed = _land(cfg, package["package_id"], stored)
        receipt = {"ok": True, "package_id": package["package_id"], "sha256": digest, "status": "landed",
                   "landed_at": state.now_iso(), "device_id": (device or {}).get("id"),
                   "file": str(landed.relative_to(state.folder(cfg))),
                   "window": {k: package["window"][k] for k in ("start_date", "end_date")}}
        state.write_json(path, receipt, private=True)
        return 200, _project_and_record(cfg, package, receipt, path)


def _project_and_record(cfg, package: Dict[str, Any], receipt: Dict[str, Any], path: Path) -> Dict[str, Any]:
    receipt = dict(receipt)
    try:
        receipt["rows"] = project(cfg, package)
        receipt["status"] = "projected"
        receipt["projected_at"] = state.now_iso()
        receipt.pop("error", None)
    except Exception as error:  # the package is safe on disk; the next start tries again
        receipt["status"] = "failed"
        receipt["error"] = f"{type(error).__name__}: {error}"
    state.write_json(path, receipt, private=True)
    return receipt


def window_bounds(cfg, package: Dict[str, Any]) -> Tuple[datetime, datetime]:
    """(local start of start_date, local moment of the read) in the configured timezone, as the tables write times."""
    window = package["window"]
    start = datetime.combine(date.fromisoformat(window["start_date"]), time(0, 0))
    end = apple_health.parse_time(window["query_end"]).astimezone(cfg.tz).replace(tzinfo=None, second=0)
    return start, max(end, start)


def project(cfg, package: Dict[str, Any]) -> Dict[str, int]:
    sessions: List[Row] = []
    meals: List[Row] = []
    rows, summary = apple_health.read_stream(io.BytesIO(to_xml(package)), cfg.tz,
                                             f"package {package['package_id']}", sessions, meals)
    first = date.fromisoformat(package["window"]["start_date"])
    last = date.fromisoformat(package["window"]["end_date"])
    start, end = window_bounds(cfg, package)
    # a nap the evening before start_date would otherwise overwrite that day's real night with a short one
    rows = [r for r in rows if first <= r["date"] <= last]
    sessions = [r for r in sessions if start <= r["start"] <= end + timedelta(minutes=1)]
    meals = [r for r in meals if start <= r["time"] <= end + timedelta(minutes=1)]
    with state.write_lock(cfg):
        apple_health.write_rows(cfg, rows, sessions, meals, summary, window=(start, end))
    return {"body_daily": len(rows), "workouts": len(sessions), "meals": len(meals)}


def lookup(cfg, package_id: str) -> Dict[str, Any]:
    if not PACKAGE_ID.match(package_id or ""):
        raise CaptureError("not a package id")
    receipt = state.read_json(_receipt_path(cfg, package_id))
    return receipt or {"package_id": package_id, "status": "not_found"}


def receipts(cfg) -> List[Dict[str, Any]]:
    folder = _folder(cfg) / "receipts"
    out = [state.read_json(p) for p in folder.glob("*.json")] if folder.is_dir() else []
    return sorted((r for r in out if r), key=lambda r: r.get("landed_at") or "")


def last_receipt(cfg) -> Optional[Dict[str, Any]]:
    found = receipts(cfg)
    return found[-1] if found else None


def retry_pending(cfg) -> int:
    """At server start: packages that landed but were not written into the tables (a crash, a bad table) get
    another try."""
    done = 0
    for receipt in receipts(cfg):
        if receipt.get("status") == "projected" or not receipt.get("file"):
            continue
        package = state.read_json(state.folder(cfg) / receipt["file"])
        if package is None:
            continue
        with _lock:
            _project_and_record(cfg, package, receipt, _receipt_path(cfg, receipt["package_id"]))
        done += 1
    return done
