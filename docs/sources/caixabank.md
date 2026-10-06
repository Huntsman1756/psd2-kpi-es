# Source: CaixaBank, S.A.

- Index: https://www.caixabank.es/empresa/bancadistancia/api-store.html
- Documents: XLSX `CaixaBank-<yyyy>Q<q>-InformeTrimestralPSD2.xlsx` (current)
  + PDFs `caixabank-<yyyy>q<q>-psd2.pdf` on imagin.com (bounded pattern probe
  for history, first observed 2024Q2).
- Parser: `caixabank` v1 (xlsx + pdf paths).

## Layout

XLSX sheet `Disponibilidad & rendimiento`: daily rows, raw ratios (0..1) —
stored ×100 as percent. Sheet `Leyenda` holds KPI definitions. PDFs: same 12
columns, single page (older) or split across pages (date+7 cells, then 5
undated HB cells zipped by row order).

Columns per interface (API=dedicated_api, Home Banking=psu_interface):
Disponibilidad | AIS TMR/%Éxito | PIS TMR/%Éxito/%Éxito consolidación.

## Peculiarities

- `% Éxito consolidación` is a different metric → its own comparability group.
- 'Leyenda': API availability uses the RTS criterion; Home Banking uses
  internal criteria → comparability is PARTIAL.
- Missing cells marked `Faltan datos`/`Sin datos` (case varies).
- 2026Q2 exists as both XLSX and PDF → dedupe prefers XLSX precision.
- imagin.com PDF history is sporadic (404s recorded as fetch-log events).
