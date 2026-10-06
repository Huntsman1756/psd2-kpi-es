# Data dictionary — observations.parquet (schema v1)

| column | type | nullable | definition | example |
|---|---|---|---|---|
| observation_id | string | no | sha-16 of the logical key (source_sha256+entity+period+interface+service+metric+raw_label) | `obs_330019215be151f3` |
| entity_id | string | no | catalog entity slug | `unicaja` |
| entity_name | string | no | legal name | `Unicaja Banco, S.A.` |
| period_start / period_end | date | no | calendar bounds of the measured period | `2025-07-01` |
| period_type | enum | no | day / month / quarter / year / unknown | `day` |
| period_label | string | no | canonical label: `YYYY-MM-DD`, `YYYY-MM`, `YYYYQQ` | `2025-07-01` |
| interface_type | enum | no | dedicated_api / web / mobile / psu_interface / other / unknown | `dedicated_api` |
| service | enum | no | AIS / PIS / PIISP / ALL / UNKNOWN | `AIS` |
| metric | enum | no | availability / downtime / response_time / error_rate / request_success_rate / request_count / other | `response_time` |
| value | float | yes | normalized numeric value (null iff not reported) | `2547.0` |
| unit | enum | no | percent / ms / seconds / count / ratio / other | `ms` |
| aggregation | enum | no | daily_mean / mean / sum / point / unknown | `daily_mean` |
| value_status | enum | no | reported / not_reported / not_applicable / ambiguous | `reported` |
| metric_definition | string | yes | publisher's stated definition, when published | see Leyenda/KPI texts |
| metric_definition_url | string | yes | where the definition was found | — |
| comparability | enum | no | DIRECT / PARTIAL / NOT_COMPARABLE / UNKNOWN | `PARTIAL` |
| comparability_group | string | no | ranking bucket (docs/comparability.md) | `response_time_daily_mean_ms` |
| source_id | string | no | `src_<sha16>` of the source artifact | `src_eb8f8b93d8b8632c` |
| source_url | string | no | exact URL fetched | — |
| source_document | string | yes | locator inside artifact | `page 2: Julio 2025` |
| published_at | date | yes | publisher-stated publication date, if known | — |
| retrieved_at | timestamp tz | yes | first fetch of this exact content | `2026-10-06 22:48:42+02` |
| source_sha256 | string | no | sha256 of the artifact bytes | — |
| parser_name / parser_version | string | no | e.g. `unicaja` / `unicaja:2` | — |
| raw_label / raw_value / raw_unit | string | yes | untransformed cell context | `Tiempo medio diario PIS` / `2547 ms` / `ms` |
| notes | string | yes | caveats (unit interpretation, segments, SLA targets) | — |

## sources.parquet

| column | type | definition |
|---|---|---|
| source_id | string | `src_<sha16>` |
| entity_id | string | owning entity |
| source_url | string | fetched URL |
| retrieved_at | timestamp | first retrieval of this content |
| http_status | int | last fetch status |
| content_type | string | last observed content type |
| filename | string | derived from URL/content-type |
| sha256 | string | content hash (joins `sources.sha256`) |
| bytes | int64 | artifact size |
| published_at | date | publisher-stated date, if known |
| period_hint | string | period parsed from URL, when available |
| parser_name / parser_version | string | intended parser |
