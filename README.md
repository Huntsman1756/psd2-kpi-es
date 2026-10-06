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

```bash
$ psd2-kpi-es compare --period 2025Q3 --metric availability
entity_id  value    unit     aggregation          comparability_group     n_days
---------  -------  -------  -------------------  ----------------------  ------
caixabank  99.993   percent  avg_of_daily         availability_daily_pct  92
renta4     90.29    percent  published_aggregate  availability_daily_pct  —
unicaja    100.0    percent  avg_of_daily         availability_daily_pct  92
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

## Roadmap

- more entities (Sabadell, Ibercaja telemetry portal, Bankinter, …)
- quarter-over-quarter mutation diffs
- static report site (v0.2+, see docs/future_frontend.md)

## License

Code: Apache-2.0. Source documents remain their publishers' content and are
not redistributed — the repo ships normalized data, hashes and acquisition
code (see docs/adr/004).
