"""Render every page to JSON files next to the web app, for hosting without a server (GitHub Pages).

Only do this with demo data or data you mean to publish: the output folder contains every number.
"""
import json
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
    index = out / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace('<html lang="en" data-theme="dusk">',
                                                              '<html lang="en" data-theme="dusk" data-static="true">'),
                     encoding="utf-8")
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
