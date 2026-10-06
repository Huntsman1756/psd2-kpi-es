# Methodology

## Pipeline (deterministic)

1. **Discovery** — each entity declares an index page in `catalog.toml`. The
   parser extracts document URLs from the fetched index HTML
   (`discover_links`) and, when needed, from inside documents
   (`discover_nested`, e.g. the XLSX linked from Santander's summary PDF).
2. **Acquisition** — httpx GET, explicit timeout, ≤2 retries, 50 MiB cap,
   identifiable `User-Agent: psd2-kpi-es/<version> (+repo-url)`. Polite: one
   request at a time, no crawling beyond discovered document links.
3. **Raw store** — content-addressed and immutable. Two retrieval events for
   the same bytes collapse onto one blob + one extra meta line; changed
   content under the same URL creates a second artifact.
4. **Parsing** — parser code reads the *local* bytes. It never guesses:
   unknown cell markers produce explicit `ParseWarning`s, and
   `-`/`NP`/`Sin datos`/`Faltan datos` markers produce *no* observation
   (recorded as absence, not zero).
5. **Normalization** — Spanish number format parsed explicitly
   (`,` decimal, `.` thousands); units normalized to {percent, ms, seconds,
   count}; services mapped to {AIS, PIS, PIISP, ALL, UNKNOWN}; interfaces to
   {dedicated_api, web, mobile, psu_interface}.
6. **Dedupe** — one observation per logical key; when the publisher ships the
   same data twice (CaixaBank xlsx+pdf), the higher-fidelity artifact wins and
   the conflict is logged (`duplicate_precision`).
7. **Validation** — value ranges, period sanity, provenance completeness,
   referential integrity. Published anomalies (e.g. negative availability)
   are kept verbatim and flagged as warnings.
8. **Publish** — sorted rows → Parquet (canonical) → DuckDB view (derived).

## Provenance contract

Every observation carries: `source_url`, `retrieved_at` (first fetch),
`source_sha256`, `source_id`, `parser_name`, `parser_version`,
`source_document` (locator inside the artifact: page / sheet / month
section), and `raw_label`/`raw_value`/`raw_unit` (the untransformed cell).

`psd2-kpi-es explain <observation_id>` renders the whole chain.

## Manual verification performed

For each parser, several rows were checked end-to-end
(document text → extracted cell → normalized value):

- Renta4 2T2024: resumen `Total 68.533 14 276 0,02% 95,81% 94,73%` →
  request_count=68533/14, response_time=276ms, error_rate=0.02%,
  availability=95.81%, sla=94.73%. Daily `02/04/24 Total 25 0 354 0,00%
  95,83%` → same fields at day level.
- Unicaja 3T2025: `17/07/2025 2547 ms 2403 ms ...` → PIS API TMR=2547ms,
  PIS canal=2403ms (page 2, July).
- CaixaBank 2025Q4: `01/10/2025 99,98% 1220 99,85% ...` → disp API=99.98%,
  AIS TMR=1220ms.
- Santander 2026Q2 XLSX: `APIs_DISP 2026-04-01 → 1` → availability=100%;
  `APIs_TMR 544.49` → 544.49ms (documented unit interpretation).

## Known transformations requiring judgment

Any value that required an interpretation rather than a literal parse is
marked `interpretation='inferred'` on the observation itself:

- Santander `APIs_TMR`: column header reads `Rendimiento (s)` but values are
  millisecond-scale; stored as ms, `raw_unit='s'`, `interpretation='inferred'`.
- Unicaja tokens damaged by PDF glyph overlaps (`ms13831383ms`): recovered
  deterministically when possible (deduplicated halves, stray unit glyphs),
  marked `interpretation='inferred'`; unrecoverable ones become warnings.
- CaixaBank/Santander XLSX ratio cells (0.9995) stored as percent (×100) —
  a definitional unit conversion, not an inference → `verbatim`.
- Renta4 `NP` cells (counts not published on the PSU interface) → absence.
