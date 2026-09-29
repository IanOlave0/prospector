import json
import sqlite3
from pathlib import Path

import pytest

from prospector import db

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def conn():
    """In-memory database with all migrations applied."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def hn_page():
    """Golden-file HN Algolia response recorded from the live API."""
    path = FIXTURES_DIR / "hackernews_search_page0.json"
    return json.loads(path.read_text(encoding="utf-8"))
