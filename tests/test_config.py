import yaml

from prospector.config import load_config, resolve_db_path


def test_shipped_config_loads():
    config = load_config()
    assert config.hackernews.enabled is True
    assert config.hackernews.queries, "at least one query must be configured"
    assert config.hackernews.hits_per_page > 0
    assert config.hackernews.base_url.startswith("https://")


def test_environment_overrides(monkeypatch, tmp_path):
    custom = tmp_path / "sources.yaml"
    custom.write_text(
        yaml.safe_dump(
            {
                "hackernews": {
                    "enabled": False,
                    "base_url": "https://example.org",
                    "endpoint": "search_by_date",
                    "hits_per_page": 5,
                    "max_pages": 1,
                    "min_points": 0,
                    "queries": ["test query"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PROSPECTOR_CONFIG", str(custom))
    config = load_config()
    assert config.hackernews.enabled is False
    assert config.hackernews.queries == ["test query"]

    monkeypatch.setenv("PROSPECTOR_DB_PATH", str(tmp_path / "custom.db"))
    assert resolve_db_path().name == "custom.db"
