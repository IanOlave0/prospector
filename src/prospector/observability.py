"""Run logging: every pipeline execution is recorded in the ``runs`` table."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from prospector.timeutils import utcnow_iso


@dataclass
class Run:
    """Live handle for a pipeline run; callers update the counters as they go."""

    id: int
    items_fetched: int = 0
    items_inserted: int = 0


@contextmanager
def record_run(conn: sqlite3.Connection, run_type: str, target: str) -> Iterator[Run]:
    """Record a run from start to finish.

    The run row is created immediately (so crashes leave a ``running`` trace),
    marked ``success`` on normal exit, or ``failed`` with the error message when
    an exception escapes. Exceptions always propagate — Prospector fails loudly.
    """
    cursor = conn.execute(
        "INSERT INTO runs (run_type, target, started_at) VALUES (?, ?, ?)",
        (run_type, target, utcnow_iso()),
    )
    conn.commit()
    run = Run(id=cursor.lastrowid)
    try:
        yield run
    except Exception as exc:
        _finish(conn, run, "failed", error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        _finish(conn, run, "success")


def _finish(conn: sqlite3.Connection, run: Run, status: str, error: str | None = None) -> None:
    conn.execute(
        """
        UPDATE runs
           SET finished_at = ?, status = ?, items_fetched = ?, items_inserted = ?, error = ?
         WHERE id = ?
        """,
        (utcnow_iso(), status, run.items_fetched, run.items_inserted, error, run.id),
    )
    conn.commit()
