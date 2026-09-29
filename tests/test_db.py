from prospector import db
from prospector.models import RawItem
from prospector.timeutils import utcnow_iso


def test_migrate_applies_initial_schema(conn):
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"raw_items", "runs"} <= tables


def test_migrate_is_idempotent(conn):
    assert db.migrate(conn) == []


def test_connect_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "prospector.db"
    conn = db.connect(path)
    conn.close()
    assert path.exists()


def test_insert_raw_items_is_idempotent(conn):
    item = RawItem(source="test", external_id="1", source_created_at=utcnow_iso(), payload="{}")
    assert db.insert_raw_items(conn, [item]) == 1
    assert db.insert_raw_items(conn, [item]) == 0
    assert conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0] == 1
