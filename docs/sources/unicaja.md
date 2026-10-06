# Source: Unicaja Banco, S.A.

- Index: https://www.unicajabanco.es/es/legales/tablon-de-anuncios
- Documents: `psd2-estadisticas-unicaja-del-{n}T{yyyy}.pdf` quarterly since
  2020; 2019 file is date-range named.
- Parser: `unicaja` v2 (positional extraction).

## Layout

Cover + alternating `Indicadores Disponibilidad <Mes>` / `Indicadores
Rendimiento <Mes>` daily tables; last page = KPI definitions (captured in
`metric_definition`). Columns: `APIs PSD2` (dedicated_api) and `Canales Online
(Web, App)` (aggregated psu_interface).

## Peculiarities

- Positional extraction: header words define column anchors because pdfminer
  sometimes merges `ms`/`%` glyphs into numbers; recoverable artifacts
  ('ms13831383ms' → duplicated digits) are cleaned deterministically.
- 2019 document: monthly KPI aggregates only (different layout) →
  period_type=month observations.
- `-` = not reported (PIISP often).
