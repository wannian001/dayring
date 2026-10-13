"""Pairing a phone with this computer, the tokens it gets, and which network addresses may talk to the server.

The rules are in docs/CAPTURE.md. In short: ``healthaio pair`` opens an 8-digit code for 10 minutes; the phone trades
it for two random tokens (one to send packages, one to read the dashboard); the server keeps only their SHA-256 and
answers only private networks and Tailscale.
"""
import hashlib
import hmac
import ipaddress
import re
import secrets
import socket
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from . import state

CODE_MINUTES = 10
CODE_TRIES = 5
LAST_SEEN_EVERY = timedelta(minutes=5)  # how often "last seen" is written back, so reads stay cheap

# who may reach `serve --lan`: home and office networks, link-local, and Tailscale's 100.64.0.0/10
NETWORKS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10",
    "fc00::/7", "fe80::/10")]
TAILNET = ipaddress.ip_network("100.64.0.0/10")

_lock = threading.Lock()


class PairingError(ValueError):
    status = 400


class WrongCode(PairingError):
    status = 403


class NoCode(PairingError):
    status = 410


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _devices_path(cfg):
    return state.folder(cfg) / "devices.json"


def _pairing_path(cfg):
    return state.folder(cfg) / "pairing.json"


def _load(cfg) -> List[Dict[str, Any]]:
    return state.read_json(_devices_path(cfg), {}).get("devices", [])


def _save(cfg, devices: List[Dict[str, Any]]) -> None:
    state.write_json(_devices_path(cfg), {"devices": devices}, private=True)


# ---------------------------------------------------------------- pairing

def open_code(cfg) -> Dict[str, str]:
    """A fresh code replaces any open one."""
    code = f"{secrets.randbelow(10 ** 8):08d}"
    salt = secrets.token_hex(16)
    expires = _now() + timedelta(minutes=CODE_MINUTES)
    with _lock:
        state.write_json(_pairing_path(cfg), {"salt": salt, "sha256": _hash(salt + code),
                                              "expires_at": expires.isoformat(timespec="seconds"), "tries": 0},
                         private=True)
    return {"code": code, "expires_at": expires.astimezone().isoformat(timespec="seconds")}


def pair(cfg, code: Any, device_name: Any, app_device_id: Any) -> Dict[str, Any]:
    if not isinstance(code, str) or not re.fullmatch(r"\d{8}", code.strip()):
        raise PairingError("the code is 8 digits")
    name = _clean_name(device_name)
    app_id = str(app_device_id or "")[:80]
    with _lock:
        path = _pairing_path(cfg)
        pending = state.read_json(path)
        expires = state.parse_iso((pending or {}).get("expires_at"))
        if not pending or expires is None or expires < _now():
            path.unlink(missing_ok=True)
            raise NoCode("no pairing code is open; run `healthaio pair` (or Pair iPhone… in the Mac app) on the computer")
        if not hmac.compare_digest(_hash(pending["salt"] + code.strip()), pending["sha256"]):
            pending["tries"] = int(pending.get("tries", 0)) + 1
            if pending["tries"] >= CODE_TRIES:
                path.unlink(missing_ok=True)
                raise WrongCode("wrong code five times; open a new one on the computer")
            state.write_json(path, pending, private=True)
            raise WrongCode("wrong or expired code")
        path.unlink(missing_ok=True)
        capture_token, read_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        devices = [d for d in _load(cfg) if not (app_id and d.get("app_device_id") == app_id)]  # pairing again replaces
        device = {"id": f"d_{secrets.token_hex(4)}", "name": name, "app_device_id": app_id,
                  "paired_at": state.now_iso(), "last_seen": None,
                  "capture_sha256": _hash(capture_token), "read_sha256": _hash(read_token)}
        devices.append(device)
        _save(cfg, devices)
    return {"device_id": device["id"], "capture_token": capture_token, "read_token": read_token}


def _clean_name(value: Any) -> str:
    text = re.sub(r"[\x00-\x1f]", "", str(value or "")).strip()
    return text[:40] or "iPhone"


def devices(cfg) -> List[Dict[str, Any]]:
    """What may be shown: never the hashes."""
    return [{k: d.get(k) for k in ("id", "name", "paired_at", "last_seen")} for d in _load(cfg)]


def revoke(cfg, device_id: Optional[str] = None, everything: bool = False) -> int:
    with _lock:
        before = _load(cfg)
        kept = [] if everything else [d for d in before if d.get("id") != device_id]
        _save(cfg, kept)
    return len(before) - len(kept)


def authenticate(cfg, token: Optional[str], kind: str) -> Optional[Dict[str, Any]]:
    """The device a token belongs to (``kind`` is "capture" or "read"), or None."""
    if not token:
        return None
    digest = _hash(token)
    field = f"{kind}_sha256"
    for device in _load(cfg):
        if hmac.compare_digest(device.get(field, ""), digest):
            _touch(cfg, device["id"], device.get("last_seen"))
            return {k: device.get(k) for k in ("id", "name", "paired_at", "last_seen")}
    return None


def _touch(cfg, device_id: str, last_seen: Optional[str]) -> None:
    seen = state.parse_iso(last_seen)
    if seen is not None and _now() - seen < LAST_SEEN_EVERY:
        return
    with _lock:
        devices = _load(cfg)
        for device in devices:
            if device.get("id") == device_id:
                device["last_seen"] = state.now_iso()
        _save(cfg, devices)


# ---------------------------------------------------------------- the network

def _address(text: str):
    try:
        ip = ipaddress.ip_address(text.split("%", 1)[0])
    except ValueError:
        return None
    mapped = getattr(ip, "ipv4_mapped", None)  # a dual-stack socket reports IPv4 clients as ::ffff:a.b.c.d
    return mapped or ip


def is_loopback(client: str) -> bool:
    ip = _address(client)
    return bool(ip and ip.is_loopback)


def allowed_source(client: str) -> bool:
    ip = _address(client)
    if ip is None:
        return False
    return ip.is_loopback or any(ip.version == n.version and ip in n for n in NETWORKS)


def host_ok(host: Optional[str]) -> bool:
    """The Host header names this computer by address, localhost, a .local name or a Tailscale name. A web page on
    another site that points its own DNS name at this computer (DNS rebinding) sends that name and is refused."""
    if not host:
        return False
    host = host.strip().lower()
    if host.startswith("["):
        name = host[1:host.find("]")] if "]" in host else ""
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if _address(name) is not None:
        return True
    return name == "localhost" or name.endswith(".local") or name.endswith(".ts.net")


def local_addresses() -> List[str]:
    """This computer's addresses a phone could use: home network first, then Tailscale."""
    found: List[str] = []
    try:
        out = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5).stdout
        found += re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)", out)
    except (OSError, subprocess.SubprocessError):
        pass
    try:  # the address of the default route, without sending anything
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 9))
        found.insert(0, probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    ordered: List[str] = []
    for text in found:
        ip = _address(text)
        if ip is None or ip.is_loopback or not allowed_source(text) or text in ordered:
            continue
        ordered.append(text)
    return sorted(ordered, key=lambda a: (_address(a) in TAILNET, ordered.index(a)))


def pair_link(url: str, code: str) -> str:
    return f"healthaio://pair?url={quote(url, safe='')}&code={code}"
