# Limitations

- **Self-reported data.** Every figure is published by the ASPSP itself under
  Art. 32(4) RTS 2018/389. This dataset is *not* independent monitoring and
  proves nothing about actual service quality.
- **Heterogeneous methodologies.** KPI names look similar across banks
  ("disponibilidad", "TDA", "TMR", "uptime") but calculation criteria differ.
  Cross-entity values are PARTIAL comparisons at best — see
  `docs/comparability.md`.
- **Incomplete coverage.** 4 entities in v0.1, chosen for format diversity,
  not representativeness. BBVA España's statistics source could not be
  located; Sabadell/Ibercaja are candidates pending investigation.
- **Shallow history for some sources.** Santander serves only the current
  quarter per asset URN; CaixaBank's imagin.com PDFs cover sporadic quarters.
- **Published anomalies kept verbatim.** e.g. Renta 4 publishes TDA=-4,17 %
  on a few days; we keep the published value and flag it. Interpretation is
  the consumer's responsibility.
- **Source mutation.** Documents change in place; `sources` rows sharing a
  `source_url` with different `sha256` expose this, but we cannot recover
  content fetched before the project existed.
- **No compliance claims.** `gaps` reports factual absence in the configured
  source as of a date — never a legal conclusion.
- **Rights on source documents.** The code is Apache-2.0. The fetched
  documents remain the publishers' content; raw artifacts are kept locally
  for reproducibility but redistribution terms are unclear, so releases ship
  normalized data + metadata + acquisition scripts rather than the PDFs/XLSX
  themselves (see ADR-004 decision in docs/limitations is noted here).
- **Santander unit ambiguity.** `APIs_TMR` header says seconds, values are
  milliseconds — interpreted and documented, could be wrong if the publisher
  meant something else.
