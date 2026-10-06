# Comparability model

Two observations are only meaningfully rankable when metric, unit,
aggregation basis and methodology align. The model encodes this on every row.

## Fields

- `comparability`: DIRECT (same publisher + same declared methodology),
  PARTIAL (aligned definition, publisher-specific methodology),
  NOT_COMPARABLE, UNKNOWN. Almost everything cross-entity is PARTIAL.
- `comparability_group`: machine-checkable bucket —
  `availability_daily_pct`, `downtime_daily_pct`,
  `response_time_daily_mean_ms`, `response_time_daily_mean_seconds`,
  `error_rate_daily_pct`, `success_rate_daily_pct`,
  `success_rate_consolidation_pct`, `request_count_daily`, `sla_target_pct`.

## Enforced rules

- `rank --comparable-only` **refuses** to run when the selected rows span more
  than one group (exit code 3). Without the flag it prints a loud warning.
- Known non-alignments in v0.1:
  - Santander channel TMR sheets are **seconds**; API TMR sheet is labelled
    "(s)" but contains milliseconds → separate group
    `response_time_daily_mean_seconds` vs `_ms`.
  - CaixaBank `% Éxito` (request success) ≠ `% Éxito consolidación`
    (settlement consolidation) → separate groups.
  - CaixaBank 'Leyenda': API availability follows the RTS criterion while
    Home Banking availability uses internal criteria → PARTIAL at best.
  - Renta4 publishes per-service availability; Unicaja/CaixaBank publish a
    single interface-wide figure.

## Cross-entity aggregation rule

`compare`/`rank` with a quarter/month/year label aggregates each entity's
**daily** observations uniformly (`avg` for rates/times, `sum` for counts)
rather than mixing published aggregates with derived ones. Rows show
`aggregation=avg_of_daily` + `n_days`.

Fallback: entities publishing only a period aggregate for the requested
service (e.g. Renta 4's ALL-service TDA exists only in the quarterly resumen)
join with `aggregation=published_aggregate`, making the mixed basis visible
in the output itself.
