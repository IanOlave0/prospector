"""SQLite storage layer: connections, schema migrations and raw-zone writes."""

import sqlite3
from pathlib import Path

from prospector.models import RawItem
from prospector.timeutils import utcnow_iso

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open the SQLite database, creating parent directories if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations in order, returning the versions applied.

    Versions are tracked with SQLite's ``user_version`` pragma. Migration files
    are named ``NNN_description.sql`` (e.g. ``001_initial.sql``); each file runs
    exactly once per database.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    applied: list[int] = []
    for migration in sorted(migrations_dir.glob("*.sql")):
        version = _migration_version(migration)
        if version <= current:
            continue
        conn.executescript(migration.read_text(encoding="utf-8"))
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
        current = version
        applied.append(version)
    return applied


def _migration_version(path: Path) -> int:
    try:
        return int(path.name.split("_", 1)[0])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Invalid migration filename: {path.name!r}") from exc


def insert_raw_items(conn: sqlite3.Connection, items: list[RawItem]) -> int:
    """Insert raw items idempotently; returns the number of *new* rows.

    Duplicates (same source + external_id) are skipped by the unique
    constraint, so re-running an extraction never duplicates data.
    """
    fetched_at = utcnow_iso()
    inserted = 0
    for item in items:
        cursor = conn.execute(
            """
            INSERT INTO raw_items (source, external_id, fetched_at, source_created_at, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (source, external_id) DO NOTHING
            """,
            (item.source, item.external_id, fetched_at, item.source_created_at, item.payload),
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted
