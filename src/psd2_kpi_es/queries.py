"""Query layer: DuckDB straight over the published Parquet files."""

from __future__ import annotations

from datetime import date

import duckdb

from psd2_kpi_es import config


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(
        "CREATE VIEW observations AS "
        f"SELECT * FROM read_parquet('{config.OBSERVATIONS_PARQUET.as_posix()}')"
    )
    con.execute(
        f"CREATE VIEW sources AS SELECT * FROM read_parquet('{config.SOURCES_PARQUET.as_posix()}')"
    )
    return con


def cols(sql: str, params: list | None = None) -> list[dict]:
    con = _con()
    try:
        cur = con.execute(sql, params or [])
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()


def coverage_rows() -> list[dict]:
    return cols(
        """
        SELECT entity_id,
               count(DISTINCT period_label) FILTER (period_type='day') AS days,
               count(DISTINCT period_label) FILTER (period_type='quarter') AS quarters,
               min(period_start) AS earliest,
               max(period_end) AS latest,
               count(DISTINCT metric) AS metrics,
               count(*) AS observations
        FROM observations
        GROUP BY entity_id ORDER BY entity_id
        """
    )


def latest_rows() -> list[dict]:
    return cols(
        """
        SELECT entity_id, period_label, metric, service, interface_type,
               value, unit, comparability_group
        FROM observations o
        WHERE value_status='reported'
          AND period_end = (SELECT max(period_end) FROM observations
                            WHERE entity_id=o.entity_id AND value_status='reported')
        ORDER BY entity_id, metric, service
        """
    )


def history_rows(
    entity_id: str,
    metric: str,
    interface: str = "dedicated_api",
    service: str = "ALL",
    granularity: str = "quarter",
) -> list[dict]:
    return cols(
        """
        SELECT period_label, period_start, value, unit, comparability_group, source_id
        FROM observations
        WHERE entity_id=? AND metric=? AND interface_type=? AND service=?
          AND period_type=? AND value_status='reported'
        ORDER BY period_start
        """,
        [entity_id, metric, interface, service, granularity],
    )


def compare_rows(
    period: str, metric: str, service: str = "ALL", interface: str = "dedicated_api"
) -> list[dict]:
    """Cross-entity comparison for a period.

    Methodology rule (docs/comparability.md): for quarter/month/year labels we
    aggregate each entity's *daily* observations uniformly — mean for
    rates/times/availability, sum for counts — instead of mixing published
    aggregates with derived ones. Result rows carry
    aggregation='derived_mean_of_daily' and n_days for auditability.
    """
    import re

    from psd2_kpi_es.parsers.base import parse_period_label

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
        return cols(
            """
            SELECT entity_id, value, unit, aggregation, comparability,
                   comparability_group, interface_type, service, 1 AS n_days
            FROM observations
            WHERE period_label=? AND metric=? AND service=? AND interface_type=?
              AND value_status='reported'
            ORDER BY entity_id
            """,
            [period, metric, service, interface],
        )
    start, end, _ptype = parse_period_label(period)
    agg = "sum" if metric == "request_count" else "avg"
    rows = cols(
        f"""
        SELECT entity_id, {agg}(value) AS value, any_value(unit) AS unit,
               '{agg}_of_daily' AS aggregation,
               min(comparability) AS comparability,
               string_agg(DISTINCT comparability_group) AS comparability_group,
               any_value(interface_type) AS interface_type,
               any_value(service) AS service,
               count(*) AS n_days
        FROM observations
        WHERE period_type='day' AND period_start>=? AND period_end<=?
          AND metric=? AND service=? AND interface_type=? AND value_status='reported'
        GROUP BY entity_id
        ORDER BY entity_id
        """,
        [start, end, metric, service, interface],
    )
    # Entities that only publish a period aggregate (e.g. Renta4's ALL-service
    # TDA exists only in the quarterly resumen) join with aggregation marked
    # 'published_aggregate' so the basis difference stays visible.
    have = {r["entity_id"] for r in rows}
    pub = cols(
        """
        SELECT entity_id, value, unit, aggregation, comparability,
               comparability_group, interface_type, service,
               NULL::int AS n_days
        FROM observations
        WHERE period_label=? AND period_type != 'day' AND metric=? AND service=?
          AND interface_type=? AND value_status='reported'
        ORDER BY entity_id
        """,
        [period, metric, service, interface],
    )
    for r in pub:
        if r["entity_id"] not in have:
            r["aggregation"] = "published_aggregate"
            rows.append(r)
    rows.sort(key=lambda r: r["entity_id"])
    return rows


def sources_rows(entity_id: str) -> list[dict]:
    return cols(
        """
        SELECT source_id, source_url, retrieved_at, sha256, bytes, filename, period_hint
        FROM sources WHERE entity_id=? ORDER BY retrieved_at
        """,
        [entity_id],
    )


def explain_row(observation_id: str) -> dict | None:
    rows = cols(
        """
        SELECT o.*, s.retrieved_at AS src_retrieved_at, s.http_status, s.filename
        FROM observations o LEFT JOIN sources s USING (source_id)
        WHERE o.observation_id = ?
        """,
        [observation_id],
    )
    return rows[0] if rows else None


def quarters_present() -> dict[str, set[str]]:
    """entity_id -> set of quarter labels with at least one daily observation."""
    out: dict[str, set[str]] = {}
    for r in cols(
        "SELECT DISTINCT entity_id, period_start FROM observations WHERE period_type='day'"
    ):
        d = r["period_start"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        out.setdefault(r["entity_id"], set()).add(f"{d.year}Q{(d.month - 1) // 3 + 1}")
    return out


def gaps_rows(today: date | None = None) -> list[dict]:
    """Facts only: fully-ended quarters with no daily data per entity.

    Absence is a fact about the configured source, not a legal conclusion.
    """
    today = today or date.today()
    if today.month > 3:
        last_complete_q_year, last_complete_q = today.year, (today.month - 1) // 3
    else:
        last_complete_q_year, last_complete_q = today.year - 1, 4
    latest_label = f"{last_complete_q_year}Q{last_complete_q}"

    def iter_quarters(start_label: str):
        y, qn = int(start_label[:4]), int(start_label[-1])
        while (y, qn) <= (last_complete_q_year, last_complete_q):
            yield f"{y}Q{qn}"
            qn += 1
            if qn == 5:
                y, qn = y + 1, 1

    rows = []
    for entity_id, present in sorted(quarters_present().items()):
        start = min(present)
        for qlab in iter_quarters(start):
            if qlab not in present and qlab <= latest_label:
                rows.append({"entity_id": entity_id, "missing_period": qlab})
    return rows
