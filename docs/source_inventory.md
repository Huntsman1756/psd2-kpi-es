# G0 — Source feasibility inventory

Investigated 2026-10-06. Every "verified" entry was actually downloaded and
text/table extraction was tested with the project's own tooling
(pdfplumber / openpyxl / httpx).

## Included in v0.1

| entity     | source_url                                                    | source_type      | periodicity | history_available              | metrics                                              | requires_js | parser_complexity | notes |
|------------|---------------------------------------------------------------|------------------|-------------|--------------------------------|------------------------------------------------------|-------------|-------------------|-------|
| renta4     | r4.com/normativa/normativa-psd2 → 25 PDFs                     | index→PDF        | quarterly   | 2019-09-14 → 2025-09-30        | TDA, TMD, TDRE, req counts; per service PIS/AIS/FCS  | no          | medium (2-col layout) | clean text layer; negative TDA anomalies published |
| unicaja    | unicajabanco.es/es/legales/tablon-de-anuncios → 27 PDFs       | index→PDF        | quarterly   | 2019-09 → 2026-06              | uptime/downtime %, TMR PIS/AIS/PIISP, error rate     | no          | medium (positional cols) | 2019 doc = monthly aggregates only; glyph-merge quirks handled positionally |
| caixabank  | caixabank.es api-store → XLSX + imagin.com PDFs               | index→XLSX/PDF   | quarterly   | 2024Q2 → 2026Q2 (sporadic)     | Disponibilidad, TMR, %Éxito, %Éxito consolidación    | no          | medium (2 formats + split tables) | Leyenda sheet documents KPI definitions; same quarter shipped twice (xlsx+pdf) |
| santander  | bancosantander.es/espacio-psd2 → PDF → XLSX (nested link)     | index→PDF→XLSX   | quarterly   | current quarter only (URN mutates) | disp per channel (web/app × particulares/empresas), TMR per API op | no | high | PDF annotation carries the XLSX URL; '(s)' column holds ms-magnitude values |

## Evaluated and not included

| candidate | status | reason |
|---|---|---|
| BBVA España | report_not_found | No public Art.32(4) stats page located for BBVA S.A. `bbvauk.com` belongs to the BE/UK entity (page cites Belgian law), not the Spanish ASPSP. |
| Ibercaja (telemetría) | conditional | `contransparencia.ibercaja.es/telemetria/psd2/` is a Highcharts JS portal; data endpoint not yet identified. Candidate for v0.2. |
| Ibercaja (imagerelay PDFs) | rejected | `links.imagerelay.com/cdn/2958/API-Statistics-*` turned out to be **Swissquote Bank Europe (LU)**, not a Spanish ASPSP — verified via document text. |
| Banco Sabadell | conditional | Page lists only the current daily-indicators PDF + quarterly dashboard; historical URLs not enumerable. May enter with bounded history. |
| Triodos | low priority | Liferay portal, JS-heavy, only last ~3 months published. Thin history. |

## G0 verdict: PASS

- ≥4 sources downloadable and deterministically parseable (4 implemented).
- Common model viable: daily {availability, downtime, response_time per
  service, error/success rates} across dedicated_api vs PSU interface.
- Volume justifies the product: ~71k normalized observations.
