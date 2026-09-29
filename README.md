# Prospector

**An automated ingestion and evaluation pipeline that mines project ideas from public
sources, filters out the noise, and ranks what is actually worth building.**

Instead of asking a chatbot for ideas and then manually reading through a hundred of
them, Prospector continuously ingests real signals — forum threads, local news, open
data — and runs every candidate through a staged, measurable evaluation cascade, so
only the strongest few ever reach you.

> **Project status:** Phase 0 — raw zone and Hacker News ingestion.
> See the [roadmap](#roadmap) for what comes next.

## Architecture

```
Extractors  ──→  Raw zone  ──→  Transform  ──→  Enrich  ──→  Evaluate  ──→  Serve  ──→  Feedback
 HN Algolia       SQLite          clean,          local        cascade       digest     👍/👎
 Reddit RSS       immutable       dedup           context      (cheap →      Telegram   feeds the
 Google News      verbatim                                       expensive)   bot        reranker
 Open data
```

Evaluation runs cheapest-first: free local embeddings cut hundreds of candidates down
to dozens, a few cheap factual lookups knock out dead ends, and only the survivors
reach the expensive LLM judge. See [`docs/architecture.md`](docs/architecture.md)
for the full design.

## Roadmap

| Phase | Deliverable |   Status    |
| :---: | ----------- | :---------: |
|   0   | Raw zone schema, run observability and Hacker News ingestion |  ✅ Done   |
|   1   | Multi-source ingestion: Reddit RSS, Google News, open data |    Next     |
|   2   | Transformations, exact dedup, rule-based baseline, weekly digest |  Planned   |
|   3   | Local enrichment (Mexico open data, regional news queries) |  Planned   |
|   4   | Embeddings: semantic dedup, novelty and relevance scoring |  Planned   |
|   5   | LLM judge (6-stage rubric) and Telegram bot with 👍/👎 feedback |  Planned   |
|   6   | Feedback-driven reranker: the rubric learns *your* weights |  Planned   |

## Quickstart

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                     # create the environment
uv run prospector init                      # create the database and apply migrations
uv run prospector extract --source hackernews
uv run prospector status
```

### CLI

| Command | Description |
| ------- | ----------- |
| `prospector init` | Create the database and apply pending migrations |
| `prospector extract --source <name>` | Run an extraction (currently: `hackernews`) |
| `prospector status` | Show raw-zone contents and recent runs |

Sources, queries and thresholds live in [`config/sources.yaml`](config/sources.yaml).
Paths can be overridden with the `PROSPECTOR_DB_PATH` and `PROSPECTOR_CONFIG`
environment variables (or a local `.env` — see `.env.example`).

## Data model

| Table | Purpose |
| ----- | ------- |
| `raw_items` | Immutable raw zone: every item stored verbatim; `UNIQUE(source, external_id)` makes ingestion idempotent |
| `runs` | Observability: one row per pipeline execution — status, counters and error |

Schema changes ship as numbered migrations in `src/prospector/db/migrations/`.

## Project layout

```
.
├── config/sources.yaml       # sources, queries and thresholds (data, not code)
├── docs/architecture.md      # design decisions behind the pipeline
├── src/prospector/
│   ├── cli.py                # init / extract / status
│   ├── config.py             # typed configuration loading
│   ├── db/                   # connections, migrations, raw-zone writes
│   ├── extractors/           # one module per source
│   └── observability.py      # run logging
└── tests/                    # pytest suite with golden fixtures
```

## Design principles

- **Immutable raw zone** — sources land verbatim; transformations never mutate raw data.
- **Idempotent by construction** — unique constraints + upserts make every re-run safe.
- **Incremental** — watermarks mean each run only fetches what is new.
- **Config as data** — queries, thresholds and (soon) evaluation rubrics live in files, not code.
- **Observable** — every run is recorded; nothing fails silently.
- **Fails loudly** — errors are logged, recorded in `runs`, and re-raised.

## Development

```bash
uv run pytest        # tests
uv run ruff check .  # lint
```

## License

[MIT](LICENSE)
