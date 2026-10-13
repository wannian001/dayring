"""Is there a newer Health AIO on GitHub, and installing it.

This is the only part of the app that goes on the internet: one request to the GitHub API, at most once every 20
hours, which sends nothing but the app's version in the User-Agent. ``[updates] check = false`` in healthaio.toml or
``HEALTHAIO_NO_UPDATE_CHECK=1`` turns it off.

A copy made with ``git clone`` is updated with a fast-forward merge to the newest release tag (never over your own
changes or commits: it stops and says so). A copy installed with pip is reinstalled from the release's archive.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import __version__, state

REPO = "wannian001/proactive-health-aio"
API = os.environ.get("HEALTHAIO_UPDATE_API", f"https://api.github.com/repos/{REPO}")
FRESH = timedelta(hours=20)
ROOT = Path(__file__).resolve().parents[1]


def cache_path() -> Path:
    base = os.environ.get("HEALTHAIO_CACHE_DIR")
    if base:
        folder = Path(base)
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Caches" / "healthaio"
    else:
        folder = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "healthaio"
    return folder / "update.json"


def parse_version(text: Optional[str]) -> Optional[Tuple[int, ...]]:
    """'v0.3.10' -> (0, 3, 10, 1). A pre-release ('0.4.0-rc1', '0.4.0b2') ends in 0, so it sorts below the release."""
    if not text:
        return None
    match = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$", text.strip())
    if not match:
        return None
    numbers = [int(part or 0) for part in match.groups()[:3]]
    rest = match.group(4)
    return (*numbers, 0 if re.search(r"[A-Za-z]", rest or "") else 1)


def newer(latest: Optional[str], current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def enabled(cfg=None) -> bool:
    if os.environ.get("HEALTHAIO_NO_UPDATE_CHECK"):
        return False
    return getattr(cfg, "check_updates", True) if cfg is not None else True


def _get(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"healthaio/{__version__}"})
    with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310 - fixed https URL
        return json.loads(response.read().decode("utf-8"))


def _latest() -> Dict[str, Any]:
    """The newest release; a repository with tags but no releases falls back to its highest v* tag."""
    try:
        release = _get(f"{API}/releases/latest")
        return {"latest": str(release.get("tag_name") or "").lstrip("v") or None,
                "tag": release.get("tag_name"), "url": release.get("html_url"),
                "notes": (release.get("body") or "")[:2000]}
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    tags: List[str] = [t.get("name", "") for t in _get(f"{API}/tags?per_page=100") if isinstance(t, dict)]
    tags = [t for t in tags if t.startswith("v") and parse_version(t)]
    if not tags:
        return {"latest": None, "tag": None, "url": None, "notes": ""}
    tag = max(tags, key=parse_version)
    return {"latest": tag.lstrip("v"), "tag": tag, "url": f"https://github.com/{REPO}/tree/{tag}", "notes": ""}


def install_kind() -> str:
    if (ROOT / ".git").exists() and (ROOT / "healthaio" / "__init__.py").is_file():
        return "git"
    if "site-packages" in str(ROOT) or "dist-packages" in str(ROOT):
        return "pip"
    return "unknown"


def _git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout)


def _blocker(kind: str) -> Optional[str]:
    """Why this copy cannot update itself, in a sentence, or None."""
    if kind == "unknown":
        return "this copy was neither cloned with git nor installed with pip; download the new version yourself"
    if kind == "git":
        try:
            dirty = _git("status", "--porcelain", "--untracked-files=no", timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "git is not available"
        if dirty:
            return "this copy has changes of your own; commit or put them aside, then update with git"
    return None


def _result(cached: Dict[str, Any]) -> Dict[str, Any]:
    kind = install_kind()
    latest = cached.get("latest")
    blocker = _blocker(kind) if newer(latest) else None
    return {"current": __version__, "latest": latest, "update_available": newer(latest),
            "url": cached.get("url"), "notes": cached.get("notes") or "", "checked_at": cached.get("checked_at"),
            "install": kind, "can_update": newer(latest) and blocker is None,
            "reason": cached.get("reason") or blocker}


def cached(cfg=None) -> Dict[str, Any]:
    """The last answer, without going online (for pages and status)."""
    if not enabled(cfg):
        return _result({"reason": "off"})
    return _result(state.read_json(cache_path(), {}) or {})


def check(cfg=None, force: bool = False) -> Dict[str, Any]:
    if not enabled(cfg):
        return _result({"reason": "off"})
    path = cache_path()
    old = state.read_json(path, {}) or {}
    checked = state.parse_iso(old.get("checked_at"))
    if not force and checked and datetime.now(timezone.utc) - checked < FRESH and old.get("current") == __version__:
        return _result(old)
    try:
        found = _latest()
        found.update(checked_at=state.now_iso(), current=__version__, reason=None)
    except (OSError, ValueError, urllib.error.URLError) as error:  # offline: keep what we knew, say why
        found = {**old, "reason": f"could not reach GitHub ({type(error).__name__})"}
        _save(path, found)
        return _result(found)
    _save(path, found)
    return _result(found)


def _save(path: Path, data: Dict[str, Any]) -> None:
    try:
        state.write_json(path, data)
    except OSError:
        pass  # a read-only home folder only means checking again next time


def _version_on_disk() -> str:
    text = (ROOT / "healthaio" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else __version__


def apply(cfg=None) -> Dict[str, Any]:
    """Install the newest release. Returns what happened; never raises for an ordinary failure."""
    info = check(cfg, force=True)
    out: Dict[str, Any] = {"ok": False, "from": __version__, "to": info.get("latest"), "method": info["install"],
                           "changed": {"mac_app": False, "ios_app": False}, "message": ""}
    if not info["update_available"]:
        out.update(ok=True, to=__version__, message=info.get("reason") or "already the newest version")
        return out
    if not info["can_update"]:
        out["message"] = info.get("reason") or "cannot update this copy"
        return out
    tag = f"v{info['latest']}"
    try:
        if info["install"] == "git":
            before = _git("rev-parse", "HEAD").stdout.strip()
            fetched = _git("fetch", "--quiet", "--tags", "origin")
            if fetched.returncode:
                out["message"] = f"git fetch failed: {fetched.stderr.strip()[-300:]}"
                return out
            target = tag if _git("rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}").returncode == 0 else "origin/main"
            merged = _git("merge", "--ff-only", "--quiet", target)
            if merged.returncode:
                out["message"] = ("your copy has commits of its own, so it cannot simply move to the new version; "
                                  f"update it with git ({merged.stderr.strip()[-200:]})")
                return out
            if _git("rev-parse", "HEAD").stdout.strip() == before:
                out.update(ok=True, to=__version__, message="this copy already has everything in that release")
                return out
            changed = _git("diff", "--name-only", before, "HEAD").stdout.split()
            out["changed"] = {"mac_app": any(p.startswith("mac/") for p in changed),
                              "ios_app": any(p.startswith("ios/") for p in changed)}
        else:
            archive = f"https://github.com/{REPO}/archive/refs/tags/{tag}.tar.gz"
            done = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", archive],
                                  capture_output=True, text=True, timeout=600)
            if done.returncode:
                out["message"] = f"pip failed: {done.stderr.strip()[-300:]}"
                return out
    except (OSError, subprocess.SubprocessError) as error:
        out["message"] = f"{type(error).__name__}: {error}"
        return out
    out["to"] = _version_on_disk() if info["install"] == "git" else info["latest"]
    out.update(ok=True, message=f"updated to {out['to']}; restart the dashboard to use it")
    old = state.read_json(cache_path(), {}) or {}
    _save(cache_path(), {**old, "current": out["to"]})
    return out
