# Future frontend (not in v0.1)

Static-first: a build step could render the Parquet dataset into a small
static site — entity pages, quarter rankings, time-series charts, a
"methodology viewer" showing the comparability group of each series, and a
missing-reports board. DuckDB/Parquet → static HTML is enough; no SPA or API
is required. If an API ever becomes necessary, the logical endpoints are
`/entities`, `/observations`, `/entities/{id}/history`,
`/periods/{p}/compare`, `/sources/{id}` — but the internal model does not
depend on HTTP.
