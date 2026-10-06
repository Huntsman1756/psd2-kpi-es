# Regulatory basis

## Norm (verified primary sources)

- **Directive (EU) 2015/2366 (PSD2)**, Art. 66/67/68: access to accounts by
  PISPs/AISPs/CBPIIs.
- **Commission Delegated Regulation (EU) 2018/389** (RTS on SCA & CSC),
  Article 32(4): ASPSPs with a dedicated interface must **make publicly
  available on their website quarterly statistics on the availability and
  performance** of that dedicated interface **and of the interface(s) used by
  their PSUs**, so that availability/performance can be compared.
- **EBA Guidelines EBA/GL/2018/07** (conditions for the Art. 33(6) exemption),
  as amended by the final report on the fallback exemption: define the KPIs —
  daily uptime %, daily downtime %, daily response time per service
  (AIS/PIS/CBPII), and a daily error-response rate — and require publication
  in a form enabling comparison with each PSU interface.
- **EBA Single Rulebook Q&A 2023_6687** (verified on eba.europa.eu): Art. 32(4)
  does not fix how long statistics must remain published; competent
  authorities may set that period. Daily statistics are published quarterly.

## Interpretation (project, not legal advice)

- Statistics are **self-reported** by each ASPSP; they are not independent
  monitoring.
- Metric definitions vary in detail between publishers (e.g. "TDA", "Tiempo
  diario de actividad", "Disponibilidad", "Uptime (%)"). Where a publisher
  states its definition (Unicaja KPI page, CaixaBank 'Leyenda' sheet), we
  capture it in `metric_definition`.
- Absence of a publication is a **fact about the configured official source**,
  never an automated compliance conclusion. `gaps` reports only facts such as
  "no report matching period YYYYQX found in the configured source as of
  YYYY-MM-DD".

## Implementation in the project

- One canonical observation per (entity, period, interface, service, metric),
  always linked to the exact source artifact (URL + SHA-256 + parser version).
- `interface_type=dedicated_api` maps to the PSD2 dedicated interface;
  PSU-facing channels map to `web`/`mobile`/`psu_interface` as published.
- The 2018/389-mandated PSU-interface comparison column exists in every
  source we ingest.

## Open questions

- Whether each entity's "interface digital/canales online" aggregation covers
  all PSU interfaces or a subset (publishers differ: Santander splits
  web/app + particulares/empresas; Unicaja and CaixaBank merge into one column).
- Whether the negative TDA values published by Renta 4 on isolated days
  (-4,17 %) are a formula artifact or a data error — reported verbatim and
  flagged, not interpreted.
- Publication cadence enforcement: some entities lag (Renta 4's index shows
  no document after 3T2025 as of 2026-10-06).
