"""macOS Screen Time (Biome ``App.InFocus``) -> ``screen_sessions``. **Experimental.**

What it reads
    ``~/Library/Biome/streams/restricted/App.InFocus/``: ``local/`` is this Mac; ``remote/<id>/``
    are other devices (iPhone, iPad, other Macs) that sync here when "Share across devices" is on
    in Screen Time settings. This is the record of foreground apps that Screen Time is built on.
    Only the user's own files are read, read-only. Biome keeps roughly four weeks, so run the
    import at least every few weeks if you want a continuous history.

Permission
    The folder is protected: the app that runs the command (Terminal, iTerm, VS Code, ...) needs
    Full Disk Access (System Settings > Privacy & Security > Full Disk Access). Without it the
    importer stops with a message saying so instead of writing an empty table.

Format (undocumented by Apple; verified against macOS files, may change with an OS update)
    SEGB v2 files: a 32-byte header starting with ``SEGB`` and the entry count; entries from offset
    0x20, each a crc32, a reserved int32 and a protobuf body, 4-byte aligned; at the end of the
    file a 16-byte index per entry (end offset relative to 0x20, state 1 = live, write time),
    the index of entry *i* starting ``16 * (i + 1)`` bytes before the end. The protobuf: field
    6 = bundle id, 3 = 1 entered / 0 left foreground, 4 = event time (seconds since 2001-01-01
    UTC), 2 = 1 app / 3 system UI. Older SEGB v1 files are reported, not read.

Sessions
    A session runs from an app entering the foreground until it leaves or another app enters.
    System UI, the lock screen and other bundle ids in ``ignore`` are not usage. A session is
    capped at 3 hours; on a Mac (which has no idle signal here) it is capped at 45 minutes
    unless the app is entertainment. A last session without an end event is dropped (the next
    import will see its end). Times are converted to the configured timezone and written at
    minute resolution: boundaries are rounded to the nearest minute, sessions that round to zero
    (under about 30 seconds) are dropped and touching sessions of the same app are joined.

Devices
    This Mac is ``laptop`` (it has a battery) or ``desktop``; ``local_device`` overrides it.
    Remote devices are named from Biome's own sync database by platform: ``phone``, ``tablet``,
    ``mac`` (this mapping is inferred from real files, not documented). Unknown ones are
    ``other``. A repeated name gets ``-2``, ``-3`` (most recently synced device first).

Categories
    ``screen_categories.json`` next to this file maps bundle ids, app names and web domains to
    ``schema.SCREEN_CATEGORIES``; a file with the same name in the data directory overrides it.
    Anything unknown is ``other``.

Merge rule
    For each device in this import, existing rows from the first imported session onwards are
    replaced; older rows and rows of other devices are kept.
"""
import json
import os
import plistlib
import sqlite3
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..schema import SCREEN_CATEGORIES, TABLES
from ._common import Row, Summary, merge_write, span, validate

STREAM = "App.InFocus"
DEFAULT_ROOT = Path.home() / "Library/Biome/streams/restricted"
SYNC_DB = Path.home() / "Library/Biome/sync/sync.db"
MAC_EPOCH = 978307200.0             # 2001-01-01T00:00:00Z as a Unix timestamp
MAX_SESSION = 3 * 3600.0
COMPUTER_CAP = 45 * 60.0
PLATFORMS = {1: "tablet", 2: "phone", 3: "mac"}
CATEGORY_FILE = "screen_categories.json"
FDA_MESSAGE = ("cannot read Screen Time data: the app running this command needs Full Disk Access. "
               "Open System Settings > Privacy & Security > Full Disk Access, turn it on for your "
               "terminal (Terminal, iTerm, VS Code, ...), restart that app and run the import again.")


class ScreenTimeError(RuntimeError):
    pass


# ---------------------------------------------------------------- categories

class Categorizer:
    """Bundle id / app name / domain -> category, from the shipped file plus the user's."""

    def __init__(self, data: Dict[str, Any]):
        self.apps: Dict[str, Dict[str, str]] = {}
        self.names: Dict[str, str] = {}
        self.domains: Dict[str, str] = {}
        self.ignore = set()
        self.problems: List[str] = []
        self.add(data)
        self._local_names: Optional[Dict[str, str]] = None

    def add(self, data: Dict[str, Any], where: str = "") -> None:
        for bundle, entry in (data.get("apps") or {}).items():
            if isinstance(entry, str):
                entry = {"category": entry}
            current = dict(self.apps.get(bundle, {}))
            current.update({k: str(v) for k, v in entry.items() if k in ("name", "category")})
            self.apps[bundle] = current
        self.names.update({str(k).lower(): str(v) for k, v in (data.get("names") or {}).items()})
        self.domains.update({str(k).lower(): str(v) for k, v in (data.get("domains") or {}).items()})
        self.ignore |= set(data.get("ignore") or [])
        for label, mapping in (("apps", {k: v.get("category", "") for k, v in self.apps.items()}),
                               ("names", self.names), ("domains", self.domains)):
            for key, category in mapping.items():
                if category and category not in SCREEN_CATEGORIES:
                    self.problems.append(f"{where or CATEGORY_FILE}: {label}[{key!r}] has unknown category "
                                         f"{category!r}; using 'other'")

    @classmethod
    def load(cls, data_dir: Optional[Path] = None) -> "Categorizer":
        shipped = Path(__file__).with_name(CATEGORY_FILE)
        categorizer = cls(json.loads(shipped.read_text(encoding="utf-8")))
        if data_dir is not None:
            own = Path(data_dir) / CATEGORY_FILE
            if own.is_file():
                try:
                    categorizer.add(json.loads(own.read_text(encoding="utf-8")), str(own))
                except ValueError as error:
                    categorizer.problems.append(f"{own}: not valid JSON ({error}); ignored")
        return categorizer

    def _ok(self, category: Optional[str]) -> Optional[str]:
        if not category:
            return None
        return category if category in SCREEN_CATEGORIES else "other"

    def category(self, app: str, bundle: Optional[str] = None) -> str:
        """Category for a bundle id, an app name or a web domain (in that order)."""
        for key in (bundle, app):
            if key and key in self.apps:
                found = self._ok(self.apps[key].get("category"))
                if found:
                    return found
        found = self._ok(self.names.get((app or "").lower()))
        if found:
            return found
        host = (app or "").lower().strip()
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0].split(":", 1)[0]
        while host:
            if host in self.domains:
                return self._ok(self.domains[host]) or "other"
            if "." not in host:
                break
            host = host.split(".", 1)[1]
        return "other"

    def name(self, bundle: str) -> str:
        entry = self.apps.get(bundle)
        if entry and entry.get("name"):
            return entry["name"]
        if self._local_names is None:
            self._local_names = installed_app_names()
        return self._local_names.get(bundle) or bundle.rsplit(".", 1)[-1] or bundle


def installed_app_names() -> Dict[str, str]:
    """Bundle id -> display name of apps installed on this Mac (Info.plist of each .app)."""
    names: Dict[str, str] = {}
    folders = [Path("/Applications"), Path("/System/Applications"), Path("/System/Applications/Utilities"),
               Path.home() / "Applications"]
    for folder in folders:
        try:
            apps = list(folder.glob("*.app"))
        except OSError:
            continue
        for app in apps:
            try:
                with (app / "Contents/Info.plist").open("rb") as handle:
                    info = plistlib.load(handle)
            except Exception:
                continue
            bundle = info.get("CFBundleIdentifier")
            label = info.get("CFBundleDisplayName") or info.get("CFBundleName") or app.stem
            if isinstance(bundle, str) and isinstance(label, str):
                names.setdefault(bundle, label)
    return names


# ---------------------------------------------------------------- SEGB / protobuf

class SegbError(ValueError):
    pass


def _varint(data: bytes, i: int) -> Tuple[int, int]:
    result = shift = 0
    while True:
        if i >= len(data):
            raise SegbError("protobuf truncated")
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, i
        if shift > 63:
            raise SegbError("protobuf varint overflow")


def parse_protobuf(data: bytes) -> Dict[int, Any]:
    """First value of each top-level field; stops at an unknown wire type."""
    fields: Dict[int, Any] = {}
    i = 0
    while i < len(data):
        key, i = _varint(data, i)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(data, i)
        elif wire == 1:
            if i + 8 > len(data):
                raise SegbError("protobuf truncated")
            value = struct.unpack_from("<d", data, i)[0]
            i += 8
        elif wire == 2:
            size, i = _varint(data, i)
            if i + size > len(data):
                raise SegbError("protobuf truncated")
            value = data[i:i + size]
            i += size
        elif wire == 5:
            if i + 4 > len(data):
                raise SegbError("protobuf truncated")
            value = data[i:i + 4]
            i += 4
        else:
            break
        fields.setdefault(number, value)
    return fields


def segb_entries(data: bytes) -> Iterator[Tuple[int, bytes]]:
    """(state, protobuf body) for each entry of a SEGB v2 file."""
    if len(data) >= 56 and data[:4] != b"SEGB" and data[52:56] == b"SEGB":
        raise SegbError("SEGB v1 file (older macOS), not supported")
    if len(data) < 0x20 or data[:4] != b"SEGB":
        raise SegbError("not a SEGB v2 file")
    count = struct.unpack_from("<i", data, 4)[0]
    if count < 0 or 0x20 + 16 * count > len(data):
        raise SegbError("bad SEGB entry count")
    position = 0x20
    for index in range(count):
        end_offset, state, _written = struct.unpack_from("<iid", data, len(data) - 16 * (index + 1))
        stop = 0x20 + end_offset
        if stop < position + 8 and state != 1:
            continue  # placeholder entry at the end of a full file
        if stop < position + 8 or stop > len(data) - 16 * count:
            raise SegbError("bad SEGB entry offset")
        yield state, data[position + 8:stop]
        position = (stop + 3) & ~3


@dataclass
class Focus:
    at: float          # Unix timestamp
    bundle: str
    entered: bool
    kind: int


def read_folder(folder: Path, since: Optional[float], errors: Dict[str, int]) -> List[Focus]:
    events: List[Focus] = []
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
    except PermissionError:
        raise ScreenTimeError(FDA_MESSAGE) from None
    for path in files:
        try:
            data = path.read_bytes()
        except PermissionError:
            raise ScreenTimeError(FDA_MESSAGE) from None
        except OSError:
            errors["unreadable file"] = errors.get("unreadable file", 0) + 1
            continue
        try:
            for state, body in segb_entries(data):
                if state != 1:
                    continue
                try:
                    fields = parse_protobuf(body)
                except SegbError:
                    errors["bad record"] = errors.get("bad record", 0) + 1
                    continue
                raw_bundle, raw_at = fields.get(6), fields.get(4)
                if not isinstance(raw_bundle, (bytes, bytearray)) or not isinstance(raw_at, float):
                    continue
                try:
                    bundle = bytes(raw_bundle).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                at = MAC_EPOCH + raw_at
                if since is not None and at < since:
                    continue
                kind = fields.get(2, 1)
                events.append(Focus(at, bundle, fields.get(3, 0) == 1, kind if isinstance(kind, int) else 0))
        except SegbError as error:
            errors[str(error)] = errors.get(str(error), 0) + 1
    return events


# ---------------------------------------------------------------- sessions

def build_sessions(events: List[Focus], device: str, categorizer: Categorizer, tz,
                   computer: bool) -> List[Row]:
    spans: List[Tuple[float, float, str]] = []
    current: Optional[Tuple[str, float]] = None

    def close(at: float) -> None:
        if current is None:
            return
        bundle, start = current
        if bundle in categorizer.ignore:
            return
        end = min(at, start + MAX_SESSION)
        if computer and categorizer.category(categorizer.name(bundle), bundle) != "entertainment":
            end = min(end, start + COMPUTER_CAP)
        if end > start:
            spans.append((start, end, bundle))

    for event in sorted(events, key=lambda e: (e.at, not e.entered)):
        if event.kind != 1:
            continue
        if event.entered:
            close(event.at)
            current = (event.bundle, event.at)
        elif current is not None and current[0] == event.bundle:
            close(event.at)
            current = None
    # the last open session has no end yet: not guessed

    rows: List[Row] = []
    for start, end, bundle in spans:
        lo, hi = _minute(start, tz), _minute(end, tz)
        if hi <= lo:
            continue
        name = categorizer.name(bundle)
        if rows and rows[-1]["app"] == name and rows[-1]["end"] >= lo:
            rows[-1]["end"] = max(rows[-1]["end"], hi)
            continue
        rows.append({"start": lo, "end": hi, "device": device, "app": name,
                     "category": categorizer.category(name, bundle)})
    return rows


def _minute(ts: float, tz) -> datetime:
    moment = datetime.fromtimestamp(round(ts / 60.0) * 60.0, timezone.utc)
    return moment.astimezone(tz).replace(tzinfo=None)


# ---------------------------------------------------------------- devices

def stream_folders(root: Path) -> List[Tuple[str, Path]]:
    base = Path(root) / STREAM
    try:
        children = os.listdir(base)
    except PermissionError:
        raise ScreenTimeError(FDA_MESSAGE) from None
    except FileNotFoundError:
        raise ScreenTimeError(f"no Screen Time stream at {base}. This importer needs macOS 13 or newer "
                              "with Screen Time turned on.") from None
    out: List[Tuple[str, Path]] = []
    if "local" in children and (base / "local").is_dir():
        out.append(("local", base / "local"))
    remote = base / "remote"
    if "remote" in children and remote.is_dir():
        try:
            for child in sorted(remote.iterdir()):
                if child.is_dir():
                    out.append((child.name, child))
        except PermissionError:
            raise ScreenTimeError(FDA_MESSAGE) from None
    return out


def remote_names(sync_db: Path) -> Dict[str, Tuple[str, float]]:
    """Remote device id -> (platform name, last sync) from Biome's sync database, if readable."""
    if not Path(sync_db).is_file():
        return {}
    rows: List[Tuple[Any, ...]] = []
    for uri in (f"{Path(sync_db).as_uri()}?mode=ro", f"{Path(sync_db).as_uri()}?mode=ro&immutable=1"):
        try:
            con = sqlite3.connect(uri, uri=True, timeout=2)
            try:
                rows = con.execute("select device_identifier, platform, last_sync_date from DevicePeer "
                                   "where coalesce(me, 0) = 0").fetchall()
            finally:
                con.close()
            break
        except sqlite3.Error:
            continue
    out: Dict[str, Tuple[str, float]] = {}
    for ident, platform, last_sync in rows:
        if isinstance(ident, str):
            out[ident] = (PLATFORMS.get(platform if isinstance(platform, int) else -1, "other"),
                          float(last_sync or 0))
    return out


def this_mac() -> str:
    try:
        text = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return "laptop"
    return "laptop" if "InternalBattery" in text else "desktop"


def label_devices(folders: List[Tuple[str, Path]], local_name: str,
                  remotes: Dict[str, Tuple[str, float]]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    used: Dict[str, int] = {local_name: 1}
    ordered = sorted((key for key, _ in folders if key != "local"),
                     key=lambda key: -remotes.get(key, ("other", 0.0))[1])
    for key in ordered:
        base = remotes.get(key, ("other", 0.0))[0]
        used[base] = used.get(base, 0) + 1
        labels[key] = base if used[base] == 1 else f"{base}-{used[base]}"
    labels["local"] = local_name
    return labels


# ---------------------------------------------------------------- entry point

@dataclass
class ScreenResult:
    rows: List[Row] = field(default_factory=list)
    devices: Dict[str, int] = field(default_factory=dict)
    errors: Dict[str, int] = field(default_factory=dict)


def read_sessions(cfg, days: int = 28, root: Path = DEFAULT_ROOT, sync_db: Path = SYNC_DB,
                  local_device: Optional[str] = None, now: Optional[float] = None,
                  categorizer: Optional[Categorizer] = None) -> ScreenResult:
    if sys.platform != "darwin" and Path(root) == DEFAULT_ROOT:
        raise ScreenTimeError("the Screen Time importer only works on macOS")
    categorizer = categorizer or Categorizer.load(cfg.data_dir)
    folders = stream_folders(Path(root))
    local_name = local_device or this_mac()
    labels = label_devices(folders, local_name, remote_names(Path(sync_db)))
    since = (now if now is not None else datetime.now(timezone.utc).timestamp()) - days * 86400.0
    result = ScreenResult()
    for key, folder in folders:
        events = read_folder(folder, since, result.errors)
        label = labels.get(key, "other")
        computer = key == "local" or label.startswith("mac")
        rows = build_sessions(events, label, categorizer, cfg.tz, computer)
        if rows:
            result.devices[label] = result.devices.get(label, 0) + len(rows)
            result.rows += rows
    return result


def import_screentime(cfg, days: int = 28, root: Path = DEFAULT_ROOT, sync_db: Path = SYNC_DB,
                      local_device: Optional[str] = None, now: Optional[float] = None) -> Summary:
    summary = Summary(table="screen_sessions", source=str(Path(root) / STREAM))
    categorizer = Categorizer.load(cfg.data_dir)
    summary.problems += categorizer.problems
    result = read_sessions(cfg, days=days, root=root, sync_db=sync_db, local_device=local_device,
                           now=now, categorizer=categorizer)
    table = TABLES["screen_sessions"]
    rows = [r for r in (validate(table, row, f"{row['device']} {row['start']}", summary.problems)
                        for row in result.rows) if r is not None]
    first_by_device: Dict[str, datetime] = {}
    for row in rows:
        if row["device"] not in first_by_device or row["start"] < first_by_device[row["device"]]:
            first_by_device[row["device"]] = row["start"]

    def drop(key: Dict[str, Any], raw: Dict[str, str]) -> bool:
        first = first_by_device.get(key["device"])
        return first is not None and key["start"] >= first

    target, total, notes = merge_write(cfg.data_dir, "screen_sessions", rows, drop=drop)
    summary.imported, summary.total, summary.path = len(rows), total, target
    summary.first, summary.last = span(rows, "start")
    summary.notes += [f"{device}: {count} sessions" for device, count in sorted(result.devices.items())]
    summary.notes += [f"{count} x {error}" for error, count in sorted(result.errors.items())]
    summary.notes += notes
    return summary
