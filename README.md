# psd2-kpi-es

An open, provenance-first dataset of **PSD2 dedicated-interface availability
and performance statistics published by Spanish ASPSPs**.

Spanish banks are required to publish quarterly statistics on the
availability and performance of their PSD2 dedicated interfaces and of the
interfaces used by their customers (Art. 32(4), Commission Delegated
Regulation (EU) 2018/389). Each bank publishes them separately, in different
formats (PDF tables, XLSX workbooks, web pages). This project fetches the
original documents, preserves them hash-addressed, and normalizes the
metrics into a single auditable dataset.

Every normalized value traces back to the exact document, page, cell text,
content hash and parser version that produced it.

```text
4 ASPSPs · 65 source artifacts · ~70k normalized observations
row-level provenance · daily + monthly + quarterly reporting
source anomalies preserved verbatim, never silently corrected
```

```bash
$ psd2-kpi-es compare --period 2025Q3 --metric availability
entity_id  value    unit     aggregation          comparability_group     n_days
---------  -------  -------  -------------------  ----------------------  ------
caixabank  99.993   percent  avg_of_daily         availability_daily_pct  92
renta4     90.29    percent  published_aggregate  availability_daily_pct  —
unicaja    100.0    percent  avg_of_daily         availability_daily_pct  92
```

```bash
$ psd2-kpi-es gaps
entity_id  missing_period
---------  --------------
caixabank  2024Q3
renta4     2025Q4
renta4     2026Q1
…
```

```bash
$ psd2-kpi-es explain obs_330019215be151f3
         entity_name: Unicaja Banco, S.A.
        period_label: 2025-07-17
       interface_type: dedicated_api
              service: ALL
               metric: availability
                value: 100.0
            raw_label: Tiempo diario actividad
            raw_value: 100%
           source_url: https://www.unicajabanco.es/content/dam/unicaja/documentos/psd2-estadisticas-unicaja-del-3T2025.pdf
         source_sha256: eb8f8b93d8b8632cf3830527f6e7bf27389d6a287324216376a78fe190ffb744
        parser_version: unicaja:2
      source_document: page 1: Julio 2025
```

## Coverage (v0.1)

| entity    | format        | history              | granularity |
|-----------|---------------|----------------------|-------------|
| Renta 4   | PDF           | 2019Q3* → 2025Q3     | daily       |
| Unicaja   | PDF           | 2019-09 → 2026Q2     | daily (+2019 monthly) |
| CaixaBank | XLSX + PDF    | 2024Q2 → 2026Q2      | daily       |
| Santander | PDF→XLSX      | current quarter      | daily       |

\* first publication starts 2019-09-14 (PSD2 go-live).

## Why ~70k rows from only 4 entities?

Volume comes from granularity, not entity count — the dataset stores **one
row per cell** of every published table:

| entity    | daily rows | other rows | total  | what drives the volume |
|-----------|-----------:|-----------:|-------:|------------------------|
| renta4    |     33,362 |        720 | 34,082 | ~2,192 days × 2 interfaces × 2 services (PIS/AIS) × ~4 KPIs |
| unicaja   |     25,939 |         44 | 25,983 | ~2,373 days × 2 interfaces × ~6 KPI columns |
| caixabank |      7,610 |         84 |  7,694 | 639 days × 2 interfaces × 6 columns |
| santander |      2,413 |          — |  2,413 | 4 PSU channels × 2 KPIs + ~18 per-operation API times |

## Quickstart

```bash
git clone https://github.com/Huntsman1756/psd2-kpi-es
cd psd2-kpi-es
uv sync
uv run psd2-kpi-es --help
uv run pytest
```

Build the dataset (fetches public documents; ~60 artifacts):

```bash
uv run psd2-kpi-es ingest renta4
uv run psd2-kpi-es ingest unicaja
uv run psd2-kpi-es ingest caixabank
uv run psd2-kpi-es ingest santander
```

or re-parse what is already in `data/raw/` offline:

```bash
uv run psd2-kpi-es build
```

## Commands

```
fetch <entity>      download index + documents into the raw store
parse <entity>      parse stored artifacts (offline)
ingest <entity>     fetch + parse + validate + publish
build               re-parse all stored artifacts, rebuild dataset

banks               catalog entities
coverage            data coverage per entity (--json)
latest              latest reported values
show <entity> --period 2025Q3
history <entity> --metric availability [--granularity day|quarter]
compare --period 2025Q3 --metric availability
rank <metric> --period 2025Q3 --comparable-only
gaps                quarters with no data found in configured sources
sources <entity>    artifacts, URLs and SHA-256
explain <obs_id>    full provenance chain of one observation
report              writes reports/latest.md
site                builds the static website into site/dist/
```

## Schema

Two Parquet files are the canonical output (`data/normalized/`):
`observations.parquet` and `sources.parquet`. DuckDB
(`dist/psd2-kpi-es.duckdb`) is derived from them. Full field reference:
[docs/data_dictionary.md](docs/data_dictionary.md).

## Methodology & comparability

These are **self-reported** statistics; definitions differ subtly between
banks. Every row carries a `comparability` flag and `comparability_group`;
`rank --comparable-only` refuses to mix incompatible groups. See
[docs/comparability.md](docs/comparability.md) and
[docs/methodology.md](docs/methodology.md).

## Limitations

Self-reported data, heterogeneous methodologies, incomplete coverage,
mutable sources, published anomalies kept verbatim. No compliance claims —
`gaps` reports facts, not verdicts. See
[docs/limitations.md](docs/limitations.md).

## Provenance

```
entity → period → document → page/cell → raw value
       → transformation → parser@version → sha256 → normalized row
```

Every row carries `raw_label`/`raw_value`/`raw_unit` (the cell as published)
plus an `interpretation` flag: `verbatim` when the cell parsed as documented,
`inferred` when a documented interpretation was required — e.g. Santander's
`Rendimiento (s)` column whose values are milliseconds despite the header,
or Unicaja tokens damaged by PDF glyph overlaps. `explain` shows all of it.

## Reproducibility — what is and isn't guaranteed

Three different claims, kept honest:

- **Verifiability**: for any observation, `explain` gives URL + SHA-256 +
  parser version; re-fetch the same URL and compare hashes, or take any raw
  artifact and re-run `build` — identical input bytes → identical dataset.
- **Reproducibility from live sources**: the acquisition code re-downloads
  every document from the publisher's URLs. This works today for all four
  entities.
- **Historical reproducibility is NOT guaranteed.** Publishers mutate or
  drop documents (Santander overwrites one stable URN each quarter;
  CaixaBank's older PDFs already 404). `data/raw/` blobs are kept locally
  but not redistributed (ADR-004), so a clean clone cannot rebuild
  yesterday's dataset if the source vanished — only artifacts you fetched
  are recoverable. This is a property of the sources, not of the pipeline.

## Web site

`uv run psd2-kpi-es site` renders the dataset to a fully static site under
`site/dist/` (HTML + JSON + SVG charts, no server runtime, no JS deps).
Deploy = rsync to any web server; reference nginx setup and the required
GitHub secrets are in [docs/deploy.md](docs/deploy.md).

## Roadmap

- more entities (Sabadell, Ibercaja telemetry portal, Bankinter, …)
- quarter-over-quarter mutation diffs

## License

Code: Apache-2.0. Source documents remain their publishers' content and are
not redistributed — the repo ships normalized data, hashes and acquisition
code (see docs/adr/004).
