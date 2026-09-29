"""Prospector command-line interface."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from prospector import __version__, db
from prospector.config import load_config, resolve_db_path
from prospector.extractors import EXTRACTORS


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    db_path = resolve_db_path(args.db_path)

    if args.command == "init":
        return _cmd_init(db_path)
    if args.command == "extract":
        return _cmd_extract(args, db_path, parser)
    if args.command == "status":
        return _cmd_status(db_path)
    parser.error(f"unknown command: {args.command}")
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prospector",
        description="Mine, evaluate and rank project ideas from public sources.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--db-path", help="SQLite database path (overrides PROSPECTOR_DB_PATH).")
    parser.add_argument("--config", help="Sources config YAML path (overrides PROSPECTOR_CONFIG).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create the database and apply pending migrations.")

    extract = subparsers.add_parser("extract", help="Run an extraction for one source.")
    extract.add_argument(
        "--source", required=True, choices=sorted(EXTRACTORS), help="Source to extract."
    )

    subparsers.add_parser("status", help="Show a summary of the database contents.")
    return parser


def _cmd_init(db_path: Path) -> int:
    conn = db.connect(db_path)
    applied = db.migrate(conn)
    if applied:
        print(f"Applied migrations: {applied}")
    else:
        print("Database is up to date.")
    print(f"Database: {db_path}")
    return 0


def _cmd_extract(args: argparse.Namespace, db_path: Path, parser: argparse.ArgumentParser) -> int:
    config = load_config(args.config)
    source_cfg = getattr(config, args.source, None)
    if source_cfg is None:
        parser.error(f"source {args.source!r} has no configuration entry")
    if not source_cfg.enabled:
        print(f"Source {args.source!r} is disabled in the configuration.")
        return 0
    conn = db.connect(db_path)
    db.migrate(conn)
    extractor = EXTRACTORS[args.source]()
    result = extractor.extract(conn, source_cfg)
    print(
        f"[{args.source}] fetched {result.items_fetched} items, "
        f"{result.items_inserted} new (run #{result.run_id})"
    )
    return 0


def _cmd_status(db_path: Path) -> int:
    conn = db.connect(db_path)
    db.migrate(conn)
    print(f"Database: {db_path}")

    total = conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0]
    print(f"\nraw_items: {total}")
    for row in conn.execute(
        """
        SELECT source, COUNT(*) AS n, MAX(source_created_at) AS newest
          FROM raw_items
         GROUP BY source
         ORDER BY source
        """
    ):
        print(f"  {row['source']:<12} {row['n']:>6}  newest: {row['newest'] or '-'}")

    runs_total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    print(f"\nruns: {runs_total} (last 5)")
    for row in conn.execute(
        """
        SELECT id, run_type, target, status, started_at, items_fetched, items_inserted, error
          FROM runs
         ORDER BY id DESC
         LIMIT 5
        """
    ):
        line = (
            f"  #{row['id']:<4} {row['run_type']}/{row['target']} [{row['status']}] "
            f"started {row['started_at']} fetched={row['items_fetched']} "
            f"new={row['items_inserted']}"
        )
        if row["error"]:
            line += f" error={row['error']}"
        print(line)
    return 0
