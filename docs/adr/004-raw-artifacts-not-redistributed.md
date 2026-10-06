# ADR-004: Source artifacts are not redistributed

## Status: accepted (v0.1)

## Context
Banks' PSD2 PDFs/XLSX are public but redistribution rights are not explicit.

## Decision
`data/raw/` is gitignored — kept locally for reproducibility. Releases ship
normalized observations + source metadata (URL, sha256, retrieval time) +
the acquisition code needed to re-fetch. The repository is self-sufficient
to rebuild the dataset from the original URLs.

## Consequences
+ No assumption that "public" == "redistributable".
+ Provenance is still fully checkable (hash + URL + parser).
− Re-fetch is needed to inspect a raw artifact on a clean clone.
