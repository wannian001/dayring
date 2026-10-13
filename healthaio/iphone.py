"""Keeping the iPhone app alive: build it from ``ios/`` with Xcode, sign it, and install it on the paired iPhone.

An app signed with a free Apple ID runs for 7 days (a paid developer account: one year). ``healthaio iphone renew``
does what you would otherwise click through in Xcode: build Release with automatic signing (your bundle id and team in
``ios/Local.xcconfig``), install with ``devicectl`` over the cable or the same Wi-Fi, and note when the new signature
runs out. The phone reads that date too and reminds you a day before.

Signing needs the login keychain, which only a session at the Mac's desktop can open: run it from Terminal, the Mac
app or the dashboard server the Mac app started, not over SSH.
"""
import os
import plistlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as config_mod, state

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "ios"
PROJECT = IOS / "HealthAIO.xcodeproj"
SCHEME = "HealthAIO"
BUILD_MINUTES = 20


def _paths(cfg) -> Dict[str, Path]:
    folder = state.folder(cfg)
    return {"last": folder / "iphone.json", "pid": folder / "iphone-renew.pid", "log": folder / "iphone-renew.log",
            "build": folder / "ios-build"}


def team() -> Optional[str]:
    local = IOS / "Local.xcconfig"
    if not local.is_file():
        return None
    match = re.search(r"^\s*HEALTHAIO_TEAM\s*=\s*([A-Z0-9]+)\s*$", local.read_text(encoding="utf-8"), re.M)
    # ABCDE12345 is the placeholder in Local.example.xcconfig: copied unchanged, it is no team at all
    return match.group(1) if match and match.group(1) != "ABCDE12345" else None


def reason() -> Optional[str]:
    """Why this computer cannot renew the app: not_macos, no_project, no_xcode, no_team; None when it can."""
    if sys.platform != "darwin":
        return "not_macos"
    if not PROJECT.is_dir():
        return "no_project"
    try:
        ok = subprocess.run(["xcodebuild", "-version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    if not ok:
        return "no_xcode"
    if not team():
        return "no_team"
    return None


def running(cfg) -> bool:
    try:
        pid = int(_paths(cfg)["pid"].read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def status(cfg) -> Dict[str, Any]:
    why = reason()
    return {"can_renew": why is None, "reason": why, "running": running(cfg),
            "last": state.read_json(_paths(cfg)["last"])}


def expiry(app: Path) -> Optional[datetime]:
    """When the app's provisioning profile runs out. The profile is a signed (CMS) wrapper around a plain plist."""
    try:
        blob = (app / "embedded.mobileprovision").read_bytes()
    except OSError:
        return None
    start, end = blob.find(b"<?xml"), blob.find(b"</plist>")
    if start < 0 or end < 0:
        return None
    try:
        value = plistlib.loads(blob[start:end + len(b"</plist>")]).get("ExpirationDate")
    except Exception:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def iphones() -> List[Dict[str, Any]]:
    """Paired physical iPhones that devicectl can see, the reachable ones first."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "devices.json"
        subprocess.run(["xcrun", "devicectl", "list", "devices", "--json-output", str(out)],
                       capture_output=True, timeout=60)
        data = state.read_json(out, {}) or {}
    found = []
    for device in (data.get("result") or {}).get("devices", []):
        hardware = device.get("hardwareProperties") or {}
        connection = device.get("connectionProperties") or {}
        if hardware.get("deviceType") != "iPhone" or hardware.get("reality") != "physical":
            continue
        if connection.get("pairingState") != "paired":
            continue
        found.append({"id": device.get("identifier"), "model": hardware.get("marketingName") or "iPhone",
                      "reachable": connection.get("tunnelState") in ("connected", "available")
                      or bool(connection.get("transportType"))})
    return sorted(found, key=lambda d: not d["reachable"])


def _log(handle, text: str) -> None:
    handle.write(f"[{state.now_iso()}] {text}\n")
    handle.flush()


def renew(cfg, device: Optional[str] = None) -> Dict[str, Any]:
    paths = _paths(cfg)
    out: Dict[str, Any] = {"ok": False, "at": state.now_iso(), "expires_at": None, "version": None,
                           "device": None, "message": ""}
    why = reason()
    if why:
        out["message"] = {"not_macos": "renewing needs a Mac with Xcode",
                          "no_project": "this copy has no ios/ folder (install from a git clone)",
                          "no_xcode": "Xcode is not installed (xcodebuild is missing)",
                          "no_team": "ios/Local.xcconfig is missing or has no HEALTHAIO_TEAM; see ios/README.md"}[why]
        out["reason"] = why
        return out
    paths["pid"].write_text(str(os.getpid()))
    try:
        with paths["log"].open("a", encoding="utf-8") as log:
            _log(log, "building the iPhone app")
            build = subprocess.run(
                ["xcodebuild", "-project", str(PROJECT), "-scheme", SCHEME, "-configuration", "Release",
                 "-destination", "generic/platform=iOS", "-derivedDataPath", str(paths["build"]),
                 "-allowProvisioningUpdates", "-allowProvisioningDeviceRegistration", "build"],
                stdout=log, stderr=subprocess.STDOUT, timeout=BUILD_MINUTES * 60, cwd=str(IOS))
            app = paths["build"] / "Build" / "Products" / "Release-iphoneos" / f"{SCHEME}.app"
            if build.returncode or not app.is_dir():
                text = paths["log"].read_text(encoding="utf-8", errors="replace")
                locked = "errSecInternalComponent" in text[-20000:]
                out["message"] = ("signing failed: the keychain is locked (run this at the Mac's desktop, not over SSH)"
                                  if locked else f"the build failed; see {paths['log']}")
                return _finish(cfg, out)
            info = plistlib.loads((app / "Info.plist").read_bytes())
            out["version"] = info.get("CFBundleShortVersionString")
            ends = expiry(app)
            out["expires_at"] = ends.astimezone().isoformat(timespec="seconds") if ends else None
            phones = iphones()
            target = next((p for p in phones if device in (None, p["id"])), None)
            if target is None:
                out["message"] = ("built, but no paired iPhone is reachable: connect it with a cable or put it on the "
                                  "same Wi-Fi, unlock it, and try again")
                return _finish(cfg, out)
            out["device"] = target["model"]
            _log(log, "installing on the iPhone")
            installed = subprocess.run(["xcrun", "devicectl", "device", "install", "app", "--device", target["id"],
                                        str(app)], stdout=log, stderr=subprocess.STDOUT, timeout=600)
            if installed.returncode:
                out["message"] = f"the install failed (is the iPhone unlocked?); see {paths['log']}"
                return _finish(cfg, out)
            out.update(ok=True, message="installed; the new signature is good until the date shown")
            _log(log, out["message"])
            return _finish(cfg, out)
    except subprocess.TimeoutExpired:
        out["message"] = "took too long; see the log"
        return _finish(cfg, out)
    finally:
        paths["pid"].unlink(missing_ok=True)


def _finish(cfg, out: Dict[str, Any]) -> Dict[str, Any]:
    state.write_json(_paths(cfg)["last"], out)
    return out


def start_background(cfg) -> Dict[str, Any]:
    """For the phone's Renew now button: run ``healthaio iphone renew`` on its own, so the request returns at once.
    It runs in this process's session, so a server started at the desktop can sign."""
    why = reason()
    if why:
        return {"started": False, "reason": why}
    if running(cfg):
        return {"started": False, "reason": "running"}
    path = config_mod.find_config(Path(cfg.root))
    command = [state.python(), "-m", "healthaio"] + (["--config", str(path)] if path else []) + ["iphone", "renew", "--json"]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")])))
    with _paths(cfg)["log"].open("a", encoding="utf-8") as log:
        subprocess.Popen(command, cwd=str(cfg.root), env=env, stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    return {"started": True}

