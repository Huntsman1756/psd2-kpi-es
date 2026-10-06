# ADR-002: No LLM in the production pipeline

## Status: accepted (v0.1)

## Context
Values are regulatory publications; every normalized number must be
reproducible and auditable.

## Decision
Extraction uses only deterministic code (pdfplumber positional logic,
openpyxl, regex over text). No OCR, no LLM inference, no embeddings.

## Consequences
+ Determinism: same artifact → same dataset.
+ Full provenance down to page/sheet/cell.
− Layout changes break parsers loudly (by design — warnings, not silence).
