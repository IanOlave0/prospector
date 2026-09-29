# Architecture

Design decisions behind Prospector. This document explains not only *what* the
pipeline does but *why* it is built this way; it is meant to stay useful as the
project grows.

## 1. Goal

Turn the manual, noisy process of "find a worthwhile project idea" into a data
pipeline: ingest public signals continuously, evaluate candidate ideas with a staged
cascade, deliver only the strongest few — and collect feedback that makes the ranking
better over time.

## 2. Layers

| Layer | Responsibility | Status |
| ----- | -------------- | ------ |
| Extract | Pull items from public APIs and feeds, politely and incrementally | In progress |
| Raw zone | Store items verbatim, immutably (`raw_items`) | Done |
| Transform | Clean, normalize, exact dedup; extract candidate ideas | Planned |
| Enrich | Local context: regional news, open data availability | Planned |
| Evaluate | The cascade (see below) | Planned |
| Serve | Weekly digest → Telegram bot | Planned |
| Feedback | 👍/👎 captured per delivered idea; trains the reranker | Planned |

## 3. The evaluation cascade

Evaluation is ordered by **cost-per-elimination**, not by rubric order:

```
A. Embeddings (free, local)   dedup + profile relevance + novelty     500 → ~60
B. Lookups (cheap, factual)   data-availability gate, saturation      ~60 → ~25
C. LLM judge (paid, slow)     full rubric over the survivors          ~25 → top-N
D. Feedback (over time)       reranker learns the user's weights
```

Two distinctions drive the design:

- **Facts vs. judgments.** "Is the market saturated?" is a *measurement* (embedding
  similarity against a corpus of existing projects), not an opinion to ask an LLM.
  Facts come from lookups; only genuine judgments reach the judge.
- **Gates vs. scores.** Data availability is oxygen: if no dataset exists, nothing
  else matters. Gates run before scores because they eliminate cheaply.

The judge rubric is versioned data (`rubric_v1`, `rubric_v2`, …) stored alongside
scores, so rubric changes can be compared on identical ideas.

### Intrinsic vs. per-user scores

Most of the rubric is intrinsic to an idea and is computed **once** and cached; only
relevance and local context are per-user. This keeps multi-user (multi-region) costs
linear in the cheap layer, not in the LLM layer.

## 4. Ingestion contract

Every extractor guarantees:

1. **Immutability** — items land in `raw_items` exactly as received (payload verbatim).
2. **Idempotency** — `UNIQUE(source, external_id)` + upserts; re-runs never duplicate.
3. **Incrementality** — a per-source watermark (newest `source_created_at`) limits each
   run to new items.
4. **Politeness** — identifiable User-Agent, timeouts, retries with exponential
   backoff, delay between requests.
5. **Fail loudly** — errors are logged, recorded in `runs`, and re-raised. Nothing is
   ever silently dropped.

## 5. Storage

SQLite, versioned with numbered migrations applied via `PRAGMA user_version`
(`src/prospector/db/migrations/`). The choice is deliberate: single-user scale makes
SQLite the fastest correct tool, and the storage layer is isolated behind
`prospector.db`, so moving to Postgres later is a contained change, not a rewrite.

## 6. Observability

Every execution writes a row to `runs` (type, target, status, counters, error).
Phase 5 reuses the delivery channel: the Telegram bot will report pipeline failures,
so the system becomes its own watchdog.

## 7. Non-goals (for now)

| Not yet | Trigger to adopt |
| ------- | ---------------- |
| Airflow / Prefect | Manual runs become annoying |
| Postgres | SQLite hurts (concurrency, size) |
| Vector database | More than ~50k ideas |
| Fine-tuning | Unlikely; a classical reranker suffices |
| Web UI | After delivery and feedback work |

## 8. Roadmap mapping

Phases build in order; each phase ends in something usable, and every layer has clean
seams (`extract` / `transform` / `score` / `serve` as separate CLI steps) so
orchestration can wrap the CLI later without rewrites. See the README roadmap table.
