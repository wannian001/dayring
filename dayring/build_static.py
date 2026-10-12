"""Render every page to JSON files next to the web app, for hosting without a server (GitHub Pages).

Only do this with demo data or data you mean to publish: the output folder contains every number.
"""
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config
from .context import Context
from .modules import PAGES, static_params
from .server import WEB, payload


def build(cfg: Config, out: Path, now: Optional[datetime] = None) -> Path:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB, out)
    version = stamp_assets(out)
    index = out / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace(
        '<html lang="en">', f'<html lang="en" data-static="true" data-build="{version}">'), encoding="utf-8")
    api = out / "api"
    api.mkdir()
    (api / "settings.json").write_text(json.dumps(cfg.public(), ensure_ascii=False), encoding="utf-8")
    ctx = Context(cfg, now=now)
    count = 1
    for name in PAGES:
        for param in static_params(name, ctx):
            data = payload(cfg, name, param, ctx.now)
            suffix = f"@{param}" if param else ""
            (api / f"{name}{suffix}.json").write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
            count += 1
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {count} data files and the web app to {out}")
    return out



IMPORT = re.compile(r'(from\s+"|import\s+")(\.{1,2}/[^"?]+\.js)"')
ASSET = re.compile(r'((?:href|src)=")((?:css|js)/[^"?]+\.(?:css|js))"')


def stamp_assets(out: Path) -> str:
    """Add ?v=<content hash> to every script and stylesheet URL, imports included.

    Static hosts let browsers cache files for minutes; without this a returning visitor can run a new
    app.js against an old i18n.js. The hash changes only when the web files change.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(out)).encode())
        digest.update(path.read_bytes())
    version = digest.hexdigest()[:10]
    for path in out.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        path.write_text(IMPORT.sub(lambda m: f'{m.group(1)}{m.group(2)}?v={version}"', text), encoding="utf-8")
    index = out / "index.html"
    index.write_text(ASSET.sub(lambda m: f'{m.group(1)}{m.group(2)}?v={version}"', index.read_text(encoding="utf-8")),
                     encoding="utf-8")
    return version
