-- 001_initial.sql — Prospector base schema.
--
-- raw_items: the immutable raw zone. Every item is stored exactly as received
-- from its source; transformations happen downstream and never mutate this table.
--
-- runs: pipeline observability. One row per execution (extract, score, ...).

CREATE TABLE raw_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,
    external_id       TEXT NOT NULL,
    fetched_at        TEXT NOT NULL,
    source_created_at TEXT,
    payload           TEXT NOT NULL,
    UNIQUE (source, external_id)
);

CREATE INDEX idx_raw_items_source_created_at
    ON raw_items (source, source_created_at);

CREATE TABLE runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type       TEXT NOT NULL,
    target         TEXT NOT NULL,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'success', 'failed')),
    items_fetched  INTEGER NOT NULL DEFAULT 0,
    items_inserted INTEGER NOT NULL DEFAULT 0,
    error          TEXT
);

CREATE INDEX idx_runs_target_started_at
    ON runs (target, started_at);
