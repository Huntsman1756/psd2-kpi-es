# Changelog

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
