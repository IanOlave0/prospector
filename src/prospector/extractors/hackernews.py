"""Hacker News extractor.

Pulls stories from the HN Algolia search API (https://hn.algolia.com/api/v1)
and lands them in the raw zone exactly as received.

Guarantees (see docs/architecture.md — "Ingestion contract"):

- Incremental: each run only fetches items newer than the stored watermark.
- Idempotent: duplicate items are skipped by the raw zone's unique constraint.
- Polite: identifiable User-Agent, timeouts, retries with backoff.
"""

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from typing import Any

import requests

from prospector.config import HackerNewsConfig
from prospector.db import insert_raw_items
from prospector.models import ExtractionResult, RawItem
from prospector.observability import Run, record_run
from prospector.timeutils import epoch_from_iso, to_utc_iso

logger = logging.getLogger(__name__)

SOURCE = "hackernews"
USER_AGENT = "prospector/0.1 (+https://github.com/; data pipeline)"
MAX_ATTEMPTS = 3


def build_search_params(
    cfg: HackerNewsConfig,
    query: str,
    page: int,
    since_epoch: int | None = None,
) -> dict[str, Any]:
    """Build query parameters for one page of the Algolia search API."""
    numeric_filters = [f"points>{cfg.min_points}"]
    if since_epoch is not None:
        numeric_filters.append(f"created_at_i>{since_epoch}")
    return {
        "query": query,
        "tags": "story",
        "hitsPerPage": cfg.hits_per_page,
        "page": page,
        "numericFilters": ",".join(numeric_filters),
    }


def parse_response(payload: dict[str, Any]) -> list[RawItem]:
    """Convert an Algolia response body into raw-zone items.

    The full hit is stored verbatim; no fields are dropped or reshaped here.
    """
    items: list[RawItem] = []
    for hit in payload.get("hits", []):
        object_id = hit.get("objectID")
        if object_id is None:
            raise ValueError(f"Hacker News hit without objectID: {hit!r}")
        created_at = hit.get("created_at")
        items.append(
            RawItem(
                source=SOURCE,
                external_id=str(object_id),
                source_created_at=to_utc_iso(created_at) if created_at else None,
                payload=json.dumps(hit, ensure_ascii=False),
            )
        )
    return items


def watermark_epoch(conn: sqlite3.Connection) -> int | None:
    """Epoch of the newest item already stored for this source (None if empty)."""
    row = conn.execute(
        """
        SELECT source_created_at
          FROM raw_items
         WHERE source = ? AND source_created_at IS NOT NULL
         ORDER BY source_created_at DESC
         LIMIT 1
        """,
        (SOURCE,),
    ).fetchone()
    if row is None:
        return None
    return epoch_from_iso(row["source_created_at"])


class HackerNewsExtractor:
    """Extract stories for every configured query, up to ``max_pages`` each."""

    name = SOURCE

    def __init__(
        self,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session or requests.Session()
        self._sleep = sleep

    def extract(self, conn: sqlite3.Connection, cfg: HackerNewsConfig) -> ExtractionResult:
        with record_run(conn, run_type="extract", target=self.name) as run:
            since_epoch = watermark_epoch(conn)
            if since_epoch is not None:
                logger.info("incremental extraction since epoch %d", since_epoch)
            for query in cfg.queries:
                self._extract_query(conn, cfg, query, since_epoch, run)
            return ExtractionResult(
                run_id=run.id,
                items_fetched=run.items_fetched,
                items_inserted=run.items_inserted,
            )

    def _extract_query(
        self,
        conn: sqlite3.Connection,
        cfg: HackerNewsConfig,
        query: str,
        since_epoch: int | None,
        run: Run,
    ) -> None:
        for page in range(cfg.max_pages):
            payload = self._fetch_page(cfg, query, page, since_epoch)
            items = parse_response(payload)
            inserted = insert_raw_items(conn, items)
            run.items_fetched += len(items)
            run.items_inserted += inserted
            logger.info("query=%r page=%d fetched=%d new=%d", query, page, len(items), inserted)
            if not items or page + 1 >= int(payload.get("nbPages", 0)):
                break
            self._sleep(cfg.request_delay_seconds)

    def _fetch_page(
        self,
        cfg: HackerNewsConfig,
        query: str,
        page: int,
        since_epoch: int | None,
    ) -> dict[str, Any]:
        url = f"{cfg.base_url}/{cfg.endpoint}"
        params = build_search_params(cfg, query, page, since_epoch)
        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._session.get(
                    url, params=params, timeout=30, headers={"User-Agent": USER_AGENT}
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "request failed (attempt %d/%d): %s", attempt + 1, MAX_ATTEMPTS, exc
                )
                if attempt + 1 < MAX_ATTEMPTS:
                    self._sleep(2**attempt)
        raise RuntimeError(
            f"Hacker News request failed after {MAX_ATTEMPTS} attempts "
            f"({type(last_error).__name__}: {last_error})"
        ) from last_error
