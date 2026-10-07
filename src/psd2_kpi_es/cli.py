"""psd2-kpi-es command line interface."""

from __future__ import annotations

import json
import logging

import typer

from psd2_kpi_es import pipeline, queries
from psd2_kpi_es.catalog import load_catalog
from psd2_kpi_es.errors import Psd2Error

app = typer.Typer(
    name="psd2-kpi-es",
    help="PSD2 availability/performance statistics published by Spanish ASPSPs.",
    no_args_is_help=True,
)

log = logging.getLogger(__name__)


def _emit(rows: list[dict], as_json: bool, columns: list[str] | None = None) -> None:
    if as_json:
        typer.echo(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        typer.echo("(no rows)")
        return
    columns = columns or list(rows[0])
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    typer.echo("  ".join(c.ljust(widths[c]) for c in columns))
    typer.echo("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        typer.echo("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def _comparability_groups(rows: list[dict]) -> set[str]:
    """All distinct comparability groups present in a result set (cells may
    carry comma-joined multi-group values from aggregation)."""
    return {g for r in rows for g in str(r.get("comparability_group", "")).split(",") if g}


def _check_dataset() -> None:
    from psd2_kpi_es import config

    if not config.OBSERVATIONS_PARQUET.exists():
        typer.echo("dataset not found: run `psd2-kpi-es ingest <entity>` first", err=True)
        raise typer.Exit(2)


# ---------------------------------------------------------------- ingest ----


@app.command()
def fetch(entity_id: str) -> None:
    """Download index + documents for an entity into the raw store."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    urls = pipeline.fetch_entity(entity_id)
    typer.echo(f"{entity_id}: {len(urls)} document URLs discovered and fetched")


@app.command()
def parse(entity_id: str) -> None:
    """Parse stored artifacts for an entity (offline)."""
    obs, arts, warns = pipeline.parse_entity(entity_id)
    typer.echo(f"{entity_id}: {len(obs)} observations from {len(arts)} artifacts")
    for w in warns:
        typer.echo(f"  warning [{w.code}] {w.message}", err=True)


@app.command()
def ingest(entity_id: str) -> None:
    """fetch + parse + validate + publish for an entity."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        res = pipeline.ingest_entity(entity_id)
    except Psd2Error as exc:
        # Typed domain failures get a dedicated exit code so schedulers can
        # distinguish e.g. SOURCE_NOT_FOUND from real breakage. stderr carries
        # a machine-readable error object.
        typer.echo(
            json.dumps({"entity": entity_id, "error_code": exc.code, "error": str(exc)}),
            err=True,
        )
        raise typer.Exit(5) from exc
    typer.echo(json.dumps(res, indent=2, default=str))


@app.command()
def build() -> None:
    """Re-parse all entities' stored artifacts and rebuild dataset (offline)."""
    all_obs, all_srcs, all_warns = [], [], []
    from psd2_kpi_es.parsers import available_parsers

    for entity_id, (_entity, srcs) in load_catalog().items():
        if srcs and srcs[0].parser not in available_parsers():
            typer.echo(f"skipping {entity_id}: parser '{srcs[0].parser}' not implemented")
            continue
        obs, arts, warns = pipeline.parse_entity(entity_id)
        all_obs += obs
        all_srcs += arts
        all_warns += warns
    violations = pipeline.publish(all_obs, all_srcs)
    typer.echo(f"published {len(all_obs)} observations, {len(all_srcs)} sources")
    for v in violations:
        typer.echo(f"  violation [{v['rule']}] {v['detail']}", err=True)
    for w in all_warns[:20]:
        typer.echo(f"  warning [{w.code}] {w.message}", err=True)


# ----------------------------------------------------------------- query ----


@app.command()
def banks(as_json: bool = typer.Option(False, "--json")) -> None:
    """List known entities."""
    rows = [
        {
            "entity_id": eid,
            "legal_name": e.legal_name,
            "website": e.website,
            "sources": len(srcs),
        }
        for eid, (e, srcs) in load_catalog().items()
    ]
    _emit(rows, as_json)


@app.command()
def coverage(as_json: bool = typer.Option(False, "--json")) -> None:
    """Data coverage per entity."""
    _check_dataset()
    _emit(queries.coverage_rows(), as_json)


@app.command()
def latest(as_json: bool = typer.Option(False, "--json")) -> None:
    """Latest reported metric values per entity."""
    _check_dataset()
    _emit(queries.latest_rows(), as_json)


@app.command()
def show(
    entity_id: str,
    period: str = typer.Option(..., "--period"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """All observations for an entity and period label (e.g. 2025Q3)."""
    _check_dataset()
    rows = queries.cols(
        """
        SELECT period_label, interface_type, service, metric, value, unit,
               aggregation, value_status, raw_label, raw_value, comparability_group
        FROM observations WHERE entity_id=? AND period_label=? ORDER BY service, metric
        """,
        [entity_id, period],
    )
    _emit(rows, as_json)


@app.command()
def history(
    entity_id: str,
    metric: str = typer.Option(..., "--metric"),
    service: str = typer.Option("ALL", "--service"),
    interface: str = typer.Option("dedicated_api", "--interface"),
    granularity: str = typer.Option("quarter", "--granularity"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Time series for an entity metric."""
    _check_dataset()
    rows = queries.history_rows(entity_id, metric, interface, service, granularity)
    _emit(rows, as_json)


@app.command()
def compare(
    period: str = typer.Option(..., "--period"),
    metric: str = typer.Option(..., "--metric"),
    service: str = typer.Option("ALL", "--service"),
    interface: str = typer.Option("dedicated_api", "--interface"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare a metric across entities for one period."""
    _check_dataset()
    rows = queries.compare_rows(period, metric, service, interface)
    groups = _comparability_groups(rows)
    if len(groups) > 1:
        typer.echo(
            f"warning: rows span {len(groups)} comparability groups "
            f"({sorted(groups)}); cross-entity comparison is PARTIAL at best",
            err=True,
        )
    _emit(rows, as_json)


@app.command()
def rank(
    metric: str,
    period: str = typer.Option(..., "--period"),
    service: str = typer.Option("ALL", "--service"),
    interface: str = typer.Option("dedicated_api", "--interface"),
    comparable_only: bool = typer.Option(False, "--comparable-only"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Rank entities by metric for a period (comparability-guarded)."""
    _check_dataset()
    rows = queries.compare_rows(period, metric, service, interface)
    groups = _comparability_groups(rows)
    if comparable_only:
        if len(groups) > 1:
            typer.echo(
                f"refused: rows span incompatible comparability groups {sorted(groups)}. "
                "Pick a single --service/--interface or drop --comparable-only.",
                err=True,
            )
            raise typer.Exit(3)
    elif len(groups) > 1:
        typer.echo(
            f"warning: mixing comparability groups {sorted(groups)}; "
            "ranking is methodologically unsafe",
            err=True,
        )
    reverse = metric not in ("response_time", "error_rate", "downtime")
    rows.sort(key=lambda r: (r["value"] is None, r["value"]), reverse=reverse)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    _emit(
        rows,
        as_json,
        ["rank", "entity_id", "value", "unit", "comparability_group", "comparability"],
    )


@app.command()
def gaps(as_json: bool = typer.Option(False, "--json")) -> None:
    """Quarters with no daily observations found in the configured sources."""
    _check_dataset()
    _emit(queries.gaps_rows(), as_json)


@app.command()
def sources(entity_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Source artifacts (URL, hash, retrieval time) for an entity."""
    _check_dataset()
    _emit(queries.sources_rows(entity_id), as_json)


@app.command()
def explain(observation_id: str, as_json: bool = typer.Option(False, "--json")) -> None:
    """Full provenance for one observation id."""
    _check_dataset()
    row = queries.explain_row(observation_id)
    if not row:
        typer.echo(f"observation {observation_id} not found", err=True)
        raise typer.Exit(4)
    if as_json:
        typer.echo(json.dumps(row, indent=2, default=str))
        return
    for k in (
        "entity_name",
        "period_label",
        "interface_type",
        "service",
        "metric",
        "value",
        "unit",
        "aggregation",
        "raw_label",
        "raw_value",
        "raw_unit",
        "interpretation",
        "comparability",
        "comparability_group",
        "source_url",
        "filename",
        "src_retrieved_at",
        "source_sha256",
        "parser_name",
        "parser_version",
        "source_document",
        "notes",
    ):
        typer.echo(f"{k:>22}: {row.get(k)}")


@app.command()
def site(
    out_dir: str | None = typer.Option(None, "--out", "-o"),
    dataset_ref: str | None = typer.Option(
        None, "--dataset-ref", envvar="PSD2_DATASET_REF"
    ),
) -> None:
    """Build the static website (HTML + JSON) into site/dist/."""
    _check_dataset()
    from pathlib import Path

    from psd2_kpi_es import sitegen

    dest = sitegen.build(Path(out_dir) if out_dir else None, dataset_ref)
    typer.echo(f"site written to {dest}")


@app.command()
def report() -> None:
    """Generate reports/latest.md from the published dataset."""
    _check_dataset()
    from datetime import date

    from psd2_kpi_es import config

    cov = queries.coverage_rows()
    latest_q = queries.cols(
        "SELECT DISTINCT period_label FROM observations "
        "WHERE period_type='quarter' ORDER BY 1 DESC LIMIT 1"
    )
    lines = [
        "# psd2-kpi-es — latest report",
        "",
        f"Generated {date.today().isoformat()} from `data/normalized/`.",
        "",
        "## Coverage",
        "",
        "| Entity | Days | Quarters | Earliest | Latest | Metrics | Observations |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in cov:
        lines.append(
            f"| {r['entity_id']} | {r['days']} | {r['quarters']} | "
            f"{r['earliest']} | {r['latest']} | {r['metrics']} | {r['observations']} |"
        )
    lines += [
        "",
        "## Latest published quarter — API availability (dedicated interface)",
        "",
        "| Entity | Availability % | Basis | n_days | Comparability |",
        "|---|---|---|---|---|",
    ]
    if latest_q:
        qlab = latest_q[0]["period_label"]
        for r in queries.compare_rows(qlab, "availability"):
            v = f"{r['value']:.2f}" if r["value"] is not None else "—"
            lines.append(
                f"| {r['entity_id']} | {v} | {r['aggregation']} | "
                f"{r.get('n_days') or '—'} | {r['comparability']} |"
            )
    gaps = queries.gaps_rows()
    lines += ["", "## Missing periods (facts only)", ""]
    if gaps:
        for g in gaps:
            lines.append(f"- {g['entity_id']}: {g['missing_period']}")
    else:
        lines.append("- none")
    lines += [
        "",
        "_Self-reported statistics; see docs/limitations.md._",
    ]
    config.REPORTS_DIR.mkdir(exist_ok=True)
    (config.REPORTS_DIR / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.echo("wrote reports/latest.md")


if __name__ == "__main__":
    app()
