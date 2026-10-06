# Source: Banco Santander, S.A.

- Index: https://www.bancosantander.es/espacio-psd2
- Documents: quarterly summary PDF (AEM asset) → links daily workbook
  `ES-estadisticas_diarias_canales_PSD2.xlsx` via PDF annotation
  (`discover_nested`).
- Parser: `santander` v1 (xlsx only; the PDF is a discovery artifact).
- Only the `santand` (Spain) PDF is used; `sucursa` (international branches)
  is deliberately ignored.

## Layout (2026Q2 workbook)

- `Resumen`: monthly availability per interface.
- `APIs_DISP` / `APIs_TMR`: daily dedicated-interface availability and
  per-operation response times (TIPO CONSUMIDOR = AIS/PIS/…).
- `Int{Particulares,Empresas}_*` = PSU web; `Mov{...}_*` = PSU mobile —
  the only source currently splitting web vs mobile and segments.

## Peculiarities

- `APIs_TMR` header says `Rendimiento (s)` but values are millisecond-scale;
  stored as ms with `notes` documenting the interpretation (raw_unit `s`).
- Channel TMR sheets really are seconds → separate comparability group.
- The asset URN is stable and overwritten each quarter → only current-quarter
  history; older content only persists if fetched in time (sha-versioned raw
  store makes mutations visible).
