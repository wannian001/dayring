"""``dayring import ...`` subcommands.

The main CLI registers them with::

    from dayring.importers import cli as import_cli
    import_cli.add_parsers(subparsers)          # subparsers = parser.add_subparsers(dest="command")
    ...
    if args.command == "import":
        return import_cli.run(args, cfg)        # cfg = dayring.config.load(...)

Commands::

    dayring import apple-health PATH                       export.zip, export.xml or the unzipped folder
    dayring import ics PATH [--kind K] [--all-day] [--days-back N] [--days-ahead N]
    dayring import macos-screentime [--days N] [--device NAME]     (experimental)
    dayring import csv TABLE PATH --map 'Source=column,...' [--date-format F] [--replace]
"""
import argparse
import sys
import zipfile
from pathlib import Path

from ..schema import EVENT_KINDS, TABLES


def add_parsers(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "import", help="bring data in from Apple Health, a calendar, Screen Time or any CSV",
        description="Read an export from another app and write it into the data directory. "
                    "See docs/IMPORTERS.md.")
    sub = parser.add_subparsers(dest="importer", metavar="SOURCE")
    sub.required = True

    health = sub.add_parser("apple-health", help="Apple Health export.zip / export.xml -> body_daily")
    health.add_argument("path", type=Path, help="export.zip, export.xml or the unzipped folder")

    ics = sub.add_parser("ics", help="calendar .ics file -> events")
    ics.add_argument("path", type=Path)
    ics.add_argument("--kind", choices=EVENT_KINDS, help="use this kind for every event in the file")
    ics.add_argument("--all-day", action="store_true", help="keep all-day events as 00:00-23:59 blocks")
    ics.add_argument("--days-back", type=int, default=180, metavar="N", help="window start (default 180)")
    ics.add_argument("--days-ahead", type=int, default=180, metavar="N", help="window end (default 180)")

    screen = sub.add_parser("macos-screentime",
                            help="macOS Screen Time (Biome) -> screen_sessions (experimental; needs Full Disk Access)")
    screen.add_argument("--days", type=int, default=28, metavar="N", help="how far back to read (default 28)")
    screen.add_argument("--device", metavar="NAME", help="name for this Mac (default laptop/desktop)")

    table = sub.add_parser("csv", help="any CSV with its own column names -> any table")
    table.add_argument("table", choices=list(TABLES))
    table.add_argument("path", type=Path)
    table.add_argument("--map", action="append", default=[], metavar="'Source=column,...'",
                       help="rename source columns to schema columns (repeatable)")
    table.add_argument("--date-format", metavar="FMT", help="strptime format of date cells, e.g. %%d/%%m/%%Y")
    table.add_argument("--datetime-format", metavar="FMT", help="strptime format of date-time cells")
    table.add_argument("--delimiter", metavar="CHAR", help="field separator (default: detected)")
    table.add_argument("--replace", action="store_true", help="rewrite the table with only this file's rows")
    return parser


def run(args, cfg) -> int:
    """Run the chosen importer, print a short summary. Returns a process exit code."""
    try:
        summary = _dispatch(args, cfg)
    except (ValueError, RuntimeError, OSError, SyntaxError, zipfile.BadZipFile) as error:
        # importers raise readable ValueError / RuntimeError subclasses; SyntaxError = broken XML
        print(f"dayring import {args.importer}: {error}", file=sys.stderr)
        return 2
    print("\n".join(summary.lines()))
    return 0


def _dispatch(args, cfg):
    if args.importer == "apple-health":
        from .apple_health import import_apple_health
        return import_apple_health(args.path, cfg)
    if args.importer == "ics":
        from .ics import import_ics
        return import_ics(args.path, cfg, kind=args.kind, days_back=args.days_back,
                          days_ahead=args.days_ahead, include_all_day=args.all_day)
    if args.importer == "macos-screentime":
        from .macos_screentime import import_screentime
        return import_screentime(cfg, days=args.days, local_device=args.device)
    if args.importer == "csv":
        from .csv_map import import_csv
        return import_csv(args.table, args.path, cfg, args.map, date_format=args.date_format,
                          datetime_format=args.datetime_format, delimiter=args.delimiter,
                          replace=args.replace)
    raise ValueError(f"unknown importer {args.importer!r}")
