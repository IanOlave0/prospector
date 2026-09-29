import json

import pytest
import requests

from prospector.config import HackerNewsConfig
from prospector.extractors.hackernews import (
    HackerNewsExtractor,
    build_search_params,
    parse_response,
    watermark_epoch,
)
from prospector.timeutils import epoch_from_iso


def make_config(**overrides) -> HackerNewsConfig:
    defaults = {
        "enabled": True,
        "base_url": "https://hn.algolia.com/api/v1",
        "endpoint": "search_by_date",
        "hits_per_page": 50,
        "max_pages": 1,
        "min_points": 3,
        "request_delay_seconds": 0.0,
        "queries": ["test query"],
    }
    defaults.update(overrides)
    return HackerNewsConfig(**defaults)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Canned HTTP session: returns pre-recorded pages in order."""

    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None, headers=None) -> FakeResponse:
        self.calls.append(params)
        page = params["page"]
        if page >= len(self.pages):
            return FakeResponse({"hits": [], "nbPages": len(self.pages), "page": page})
        return FakeResponse(self.pages[page])


class FailingSession:
    """HTTP session that always raises a connection error."""

    def get(self, *args, **kwargs):
        raise requests.ConnectionError("network down")


def test_build_search_params_applies_point_filter():
    params = build_search_params(make_config(min_points=10), "ideas", page=0)
    assert params["numericFilters"] == "points>10"
    assert params["tags"] == "story"
    assert params["query"] == "ideas"


def test_build_search_params_applies_watermark():
    params = build_search_params(make_config(), "ideas", page=1, since_epoch=1788000000)
    assert "points>3" in params["numericFilters"]
    assert "created_at_i>1788000000" in params["numericFilters"]
    assert params["page"] == 1


def test_parse_response_maps_hits_to_raw_items(hn_page):
    items = parse_response(hn_page)
    assert [item.external_id for item in items] == ["44700111", "44700222", "44700333"]
    assert all(item.source == "hackernews" for item in items)
    assert items[0].source_created_at == "2026-09-01T10:00:00Z"
    # the payload round-trips the exact hit
    assert json.loads(items[0].payload) == hn_page["hits"][0]


def test_parse_response_rejects_hits_without_object_id():
    with pytest.raises(ValueError, match="objectID"):
        parse_response({"hits": [{"title": "missing id"}]})


def test_extraction_is_idempotent(conn, hn_page):
    extractor = HackerNewsExtractor(session=FakeSession([hn_page]), sleep=lambda _: None)
    cfg = make_config()

    first = extractor.extract(conn, cfg)
    assert (first.items_fetched, first.items_inserted) == (3, 3)

    second = extractor.extract(conn, cfg)
    assert (second.items_fetched, second.items_inserted) == (3, 0)

    assert conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0] == 3


def test_extraction_uses_watermark_on_next_run(conn, hn_page):
    session = FakeSession([hn_page])
    extractor = HackerNewsExtractor(session=session, sleep=lambda _: None)
    cfg = make_config()

    extractor.extract(conn, cfg)
    expected = epoch_from_iso("2026-09-05T14:30:00Z")
    assert watermark_epoch(conn) == expected

    extractor.extract(conn, cfg)
    assert f"created_at_i>{expected}" in session.calls[1]["numericFilters"]


def test_extraction_records_successful_run(conn, hn_page):
    extractor = HackerNewsExtractor(session=FakeSession([hn_page]), sleep=lambda _: None)
    result = extractor.extract(conn, make_config())

    row = conn.execute("SELECT * FROM runs WHERE id = ?", (result.run_id,)).fetchone()
    assert row["run_type"] == "extract"
    assert row["target"] == "hackernews"
    assert row["status"] == "success"
    assert row["items_fetched"] == 3
    assert row["items_inserted"] == 3
    assert row["finished_at"] is not None
    assert row["error"] is None


def test_failed_extraction_is_recorded_and_reraised(conn):
    extractor = HackerNewsExtractor(session=FailingSession(), sleep=lambda _: None)

    with pytest.raises(RuntimeError, match="after 3 attempts"):
        extractor.extract(conn, make_config())

    row = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "failed"
    assert "ConnectionError" in row["error"]
