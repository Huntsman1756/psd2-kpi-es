# Source: Renta 4 Banco, S.A.

- Index: https://www.r4.com/normativa/normativa-psd2
- Documents: `PublicacionEstadisticasRenta4_PSD2[_nTyy].pdf` — one per quarter,
  first covers 2019-09-14→2019-12-31 (partial).
- Parser: `renta4` v1.

## Layout

Page 0 `Resumen`: quarterly aggregates per service (Total/PIS/AIS/FCS/PCOMUNES)
for INTERFAZ APIs (dedicated_api) and INTERFAZ DIGITAL (psu_interface), side by
side. Pages 1+: daily tables per ASPSP_<service> section; extract_text merges
the two half-tables per line — rows are split on the second date.

KPIs: Peticiones OK/KO (count), TMD (ms), TDRE (%), TDA (%), OBJETIVO TDA
(sla target → metric=other).

## Peculiarities

- `NP` = not published (counts on the PSU interface).
- Some daily rows omit TDRE → absent, not zero.
- Publisher anomaly: TDA = −4,17 % on isolated days; kept verbatim.
- As of 2026-10-06, index lists no document after 3T2025 (`gaps` shows it).
