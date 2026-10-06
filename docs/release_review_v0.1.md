# Release review — v0.1.0 (2026-10-06)

Six-perspective review. Evidence referenced inline.

## Product — PASS

Does it answer a question that previously required visiting multiple bank
sites? Yes: `compare --period 2025Q3 --metric availability` answers the
cross-entity availability question in one command, and `explain` answers
"where does this number come from" end-to-end. `gaps` surfaces Renta 4's
publication lag (no docs after 3T2025) and CaixaBank's missing 2024Q3 as
facts.

## Data engineering — PASS

Provenance: every observation carries URL + first-fetch timestamp + SHA-256 +
parser@version + in-document locator + raw cell. Raw store is
content-addressed/immutable; a mutated URL yields a second artifact row
(verified: dedupe logic exercised live by CaixaBank's xlsx/pdf double
publication). Same raw set → same logical dataset (observation ids and row
order are deterministic).

## Backend / architecture — CONDITIONAL PASS

Small layered pipeline, no speculative abstractions (single 500-line parser
for the hardest entity). Two known seams to revisit: `pipeline._dedupe`
preference rule (xlsx>pdf) is a heuristic encoded in code rather than
configuration; and Santander's parser only handles the *current* XLSX shape.

## QA — PASS

26 tests green: golden tests over real fixtures for all 4 parsers (full-row
diff on parser change), unit tests for number/date/period normalization,
validation rules (range/period/provenance/duplicates/referential), dedupe
conflict cases, comparability-group guard. Manual verification of extracted
values against source documents documented in docs/methodology.md.

## Security / supply chain — PASS

No credentials anywhere (all sources are public). Identifiable User-Agent;
explicit timeouts; ≤2 retries; 50 MiB artifact cap; no execution of
downloaded content; no decompression; index→document→nested-document
crawling only (bounded). Actions use minimal `contents: read` permissions;
no secrets; refresh produces artifacts, no auto-commit. Dependencies are
few, mainstream and pinned via `uv.lock`. Windows/dev path handling uses
`pathlib` throughout.

## Open-source usability — PASS

`uv sync` + `uv run psd2-kpi-es --help` + `uv run pytest` work on a clean
clone; tests need no network (fixtures+goldens committed). README states
problem, coverage, commands, schema pointer, methodology, limitations.
Licensing stance explicit (code Apache-2.0; source documents not
redistributed).

## Verdict

**v0.1.0 ready.** Two documented debts for v0.2: Santander has only
current-quarter history (source limitation, not a bug), and no fifth entity
yet — Ibercaja's telemetry portal needs an XHR endpoint investigation.
