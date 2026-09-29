"""Shared data structures that move through the pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RawItem:
    """A single item landed in the raw zone, exactly as received from its source."""

    source: str
    external_id: str
    source_created_at: str | None
    payload: str  # JSON text, verbatim


@dataclass
class ExtractionResult:
    """Outcome of one extraction run."""

    run_id: int
    items_fetched: int
    items_inserted: int
