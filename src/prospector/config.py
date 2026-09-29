"""Configuration loading.

Everything that varies (sources, queries, thresholds) lives in config files,
not in code. Environment variables can override file locations:

- ``PROSPECTOR_CONFIG``: path to the sources YAML (default: ``config/sources.yaml``)
- ``PROSPECTOR_DB_PATH``: path to the SQLite database (default: ``data/prospector.db``)
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "prospector.db"


@dataclass(frozen=True)
class HackerNewsConfig:
    enabled: bool
    base_url: str
    endpoint: str
    hits_per_page: int
    max_pages: int
    min_points: int
    request_delay_seconds: float
    queries: list[str]


@dataclass(frozen=True)
class SourcesConfig:
    hackernews: HackerNewsConfig


def load_config(path: str | Path | None = None) -> SourcesConfig:
    """Load and validate the sources configuration."""
    config_path = Path(path or os.environ.get("PROSPECTOR_CONFIG", DEFAULT_CONFIG_PATH))
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    hn = raw["hackernews"]
    return SourcesConfig(
        hackernews=HackerNewsConfig(
            enabled=bool(hn["enabled"]),
            base_url=str(hn["base_url"]).rstrip("/"),
            endpoint=str(hn["endpoint"]),
            hits_per_page=int(hn["hits_per_page"]),
            max_pages=int(hn["max_pages"]),
            min_points=int(hn["min_points"]),
            request_delay_seconds=float(hn.get("request_delay_seconds", 1.0)),
            queries=list(hn["queries"]),
        )
    )


def resolve_db_path(path: str | Path | None = None) -> Path:
    """Resolve the database path from argument, environment, or default."""
    return Path(path or os.environ.get("PROSPECTOR_DB_PATH", DEFAULT_DB_PATH))
