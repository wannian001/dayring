"""dayring command line.

    python -m dayring demo                 # write a demo folder (made-up person) and print how to open it
    python -m dayring serve --demo         # try it at once with demo data
    python -m dayring serve                # your own data: reads ./dayring.toml
    python -m dayring build-static --demo  # the GitHub Pages site (demo data only)
    python -m dayring check                # validate your data files
    python -m dayring import ...           # bring data in (Apple Health, .ics, Screen Time, any CSV)
"""
import argparse
import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from . import config as config_mod
from . import demo as demo_mod
from .schema import TABLES, describe_markdown


def _config(args) -> config_mod.Config:
    if getattr(args, "demo", False):
        folder = Path(tempfile.mkdtemp(prefix="dayring-demo-"))
        today = date.fromisoformat(args.today) if getattr(args, "today", None) else None
        path = demo_mod.generate(folder, today)
        return config_mod.load(path)
    path = Path(args.config) if args.config else config_mod.find_config(Path.cwd())
    if path is None:
        sys.exit("No dayring.toml here. Copy examples/dayring.example.toml, or try `python -m dayring serve --demo`.")
    return config_mod.load(path)


def _now(args) -> Optional[datetime]:
    if getattr(args, "now", None):
        return datetime.fromisoformat(args.now)
    if getattr(args, "demo", False) and args.command != "serve" or getattr(args, "today", None):
        # the demo person's day was generated up to 18:40; pages must agree on what "now" is
        day = date.fromisoformat(args.today) if getattr(args, "today", None) else date.today()
        return datetime.combine(day, datetime.min.time()).replace(hour=18, minute=40)
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="dayring", description="A local-first dashboard for your day.")
    parser.add_argument("--config", help="path to dayring.toml (default: ./dayring.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the dashboard on this computer")
    p.add_argument("--demo", action="store_true", help="use a made-up person instead of your data")
    p.add_argument("--today", help="demo only: pretend today is YYYY-MM-DD")
    p.add_argument("--now", help="pretend the current time is YYYY-MM-DDTHH:MM")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8790)

    p = sub.add_parser("demo", help="write a demo folder you can open and edit")
    p.add_argument("--out", default="dayring-demo")
    p.add_argument("--today", help="pretend today is YYYY-MM-DD")

    p = sub.add_parser("build-static", help="render a static site (for GitHub Pages)")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--today")
    p.add_argument("--now")
    p.add_argument("--out", default="site")
    p.add_argument("--i-understand-this-publishes-my-data", dest="publish_own", action="store_true",
                   help="required to build from your own data instead of the demo")

    sub.add_parser("check", help="validate the CSV files in the data folder")
    p = sub.add_parser("schema", help="print the data format")
    p.add_argument("--markdown", action="store_true")
    p = sub.add_parser("page", help="print one page's JSON (for scripts and assistants)")
    p.add_argument("name")
    p.add_argument("param", nargs="?")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--today")
    p.add_argument("--now")

    try:
        from .importers import cli as importers_cli
        importers_cli.add_parsers(sub)
    except Exception:  # importers are optional; a broken one must not block serve
        importers_cli = None

    args = parser.parse_args(argv)
    if args.command == "schema":
        if args.markdown:
            print(describe_markdown())
        else:
            print(json.dumps({n: [c.name for c in t.columns] for n, t in TABLES.items()}, indent=2))
        return 0
    if args.command == "demo":
        today = date.fromisoformat(args.today) if args.today else None
        path = demo_mod.generate(Path(args.out), today)
        print(f"Demo written to {path.parent}. Open it with:\n  python -m dayring --config {path} serve")
        return 0
    if args.command == "import":
        if importers_cli is None:
            sys.exit("importers are not installed")
        return importers_cli.run(args, _config(args))

    cfg = _config(args)
    if args.command == "serve":
        from .server import serve
        fixed = _now(args)
        serve(cfg, host=args.host, port=args.port, now=lambda: fixed)
        return 0
    if args.command == "build-static":
        if not (cfg.demo or args.publish_own):
            sys.exit("build-static writes every number into public files. Use --demo, or add "
                     "--i-understand-this-publishes-my-data if you really mean to publish your own.")
        from .build_static import build
        build(cfg, Path(args.out), now=_now(args))
        return 0
    if args.command == "page":
        from .server import payload
        print(json.dumps(payload(cfg, args.name, args.param, _now(args)), ensure_ascii=False, indent=2, default=str))
        return 0
    if args.command == "check":
        from .store import Store
        store = Store(cfg.data_dir)
        bad = 0
        for name, table in TABLES.items():
            loaded = store.load(name)
            state = f"{len(loaded.rows)} rows" if loaded.present else "missing (optional)"
            print(f"{table.filename:22} {state}")
            for problem in loaded.problems[:20]:
                bad += 1
                print(f"  line {problem.line}, {problem.column}: {problem.message}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
