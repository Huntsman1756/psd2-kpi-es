# Changelog

## [Unreleased]

- `deploy-site.yml` no longer ingests live sources: it deploys only
  reviewed datasets — downloads `observations.parquet`/`sources.parquet`
  from a GitHub release, verifies SHA-256 against `SHA256SUMS`, builds and
  rsyncs. Trigger: `workflow_dispatch` (optional `dataset_ref`) or release
  published.
- VPS deploy hardened: SSH host key pinned via `VPS_HOST_KEY` secret
  (`StrictHostKeyChecking=yes`, no trust-on-first-use); docs specify a
  dedicated unprivileged `psd2-deploy` user.
- Site footer shows the dataset release it was built from (`--dataset-ref`
  / `PSD2_DATASET_REF`), build time and app version — a deployed page is
  traceable to a reviewed dataset.
- Post-deploy smoke test in `deploy-site.yml`: the run is green only when
  the public URL serves the generated files (not just when rsync exits 0).

## [0.1.1] — 2026-10-07

Hardening + static web presence. No dataset schema changes.

- CI: `mypy` is now a real gate (was `|| true` informational).
- `ingest` maps typed domain errors to exit code 5 with a machine-readable
  `{"error_code": ...}` on stderr; `scripts/ingest_all.sh` tracks per-entity
  outcomes — `SOURCE_NOT_FOUND` is reported as a modelled absence while real
  failures (network/parse/validation/zero observations) fail the refresh.
- New `site` command: renders the dataset to a fully static site under
  `site/dist/` (HTML + JSON, no server runtime) — overview, entities,
  compare, history and provenance pages.
- `parse_period_label` accepts explicit range labels (`YYYY-MM-DD_YYYY-MM-DD`)
  — fixes `compare` on labels like `2019-09-14_2019-12-16`.
- `deploy-site.yml` workflow: monthly build + rsync deploy to a VPS
  (nginx), see docs/deploy.md.

## [0.1.0] — 2026-10-06

Initial release.

- Entities: Renta 4 (PDF, 2019→2025Q3), Unicaja (PDF, 2019→2026Q2),
  CaixaBank (XLSX+PDF, 2024Q2→2026Q2), Santander (PDF→XLSX, current quarter).
- Provenance-first pipeline: immutable sha256 raw store, deterministic
  parsers, `raw_*` fields on every observation.
- Canonical Parquet dataset + derived DuckDB + Typer CLI
  (banks/coverage/latest/show/history/compare/rank/gaps/sources/explain).
- Comparability model with hard guard in `rank --comparable-only`.
- `interpretation` column: `verbatim` vs `inferred` for values that required
  a documented interpretation (Santander's ms-labelled-as-seconds column,
  Unicaja glyph-recovered cells).
- Published anomalies preserved verbatim and flagged (Renta 4 TDA=-4,17 %
  has a permanent regression fixture + test).
- Golden tests over real fixtures; validation rules; CI + monthly refresh
  workflow (artifacts, no auto-commit).
