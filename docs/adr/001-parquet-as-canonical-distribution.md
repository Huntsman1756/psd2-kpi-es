# ADR-001: Parquet as canonical distribution; DuckDB derived

## Status: accepted (v0.1)

## Context
The dataset must be queryable, portable, and reproducible without the app.

## Decision
`data/normalized/*.parquet` is the canonical, versioned output.
`dist/psd2-kpi-es.duckdb` is a convenience view rebuilt from Parquet and
never a source of truth.

## Consequences
+ Parquet is language-agnostic, diffable via tooling, CI-friendly.
− Two artifacts to publish; the DuckDB build step must always derive.
