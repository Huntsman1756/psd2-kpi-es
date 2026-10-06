# Architecture

```
source discovery (index pages / declared patterns)
        ↓
acquisition        httpx, timeout+retries, size cap, identifiable UA
        ↓
raw artifact store content-addressed: data/raw/<entity>/blobs/<sha256>
        ↓           immutable; retrieval events appended as jsonl metadata
source-specific    parser module per entity: artifact bytes → canonical obs
parser             (offline only; never does I/O)
        ↓
dedupe + validate  logical-key dedupe; range/provenance/integrity rules
        ↓
Parquet            data/normalized/{observations,sources}.parquet  (canonical)
        ↓
DuckDB             dist/psd2-kpi-es.duckdb (derived convenience view)
        ↓
CLI / reports      queries read Parquet directly via DuckDB
```

Layers are separated deliberately: `fetch` only writes raw bytes + metadata;
`parse`/`build` work fully offline from the raw store.

## Key decisions (see docs/adr/)

- ADR-001: Parquet is the canonical published format; DuckDB is derived.
- ADR-002: no LLM in the production pipeline — deterministic parsers only.
- ADR-003: comparability is modeled per observation
  (`comparability` + `comparability_group`), not per entity.

## Components

- `models.py` — enums + pydantic contract (schema v1), deterministic
  `observation_id` = sha of the logical key.
- `catalog.toml` — declarative entity/source config; parsers stay code.
- `acquisition/` — `fetch.py` (http) + `rawstore.py` (immutable store).
- `parsers/` — `base.py` (protocol + period helpers), `textnorm.py`
  (Spanish number/date formats), one module per entity with
  `discover_links`, optional `discover_nested`, `period_hint`, `parse`.
- `pipeline.py` — fetch_entity / parse_entity / publish / ingest_entity.
- `validation/rules.py` — dataset rules; violations have severities.
- `storage/` — parquet writer (stable sort → deterministic output),
  duckdb builder.
- `queries.py` — SQL for every CLI command.
- `cli.py` — Typer app.

## Mutations of source documents

URLs are unstable identifiers: the same URL may serve new content (Santander's
XLSX URN, Sabadell's "current" PDF). Blobs are keyed by SHA-256, so a changed
document yields a *new* artifact row; previous versions stay. A URL whose
content changed is visible as multiple `sources` rows sharing `source_url`
with different `sha256`.
