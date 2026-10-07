"""Static site builder: renders the published dataset to HTML + JSON.

Reads data/normalized/*.parquet through the query layer and emits a fully
static site under site/dist/ — HTML pages, JSON data files and copied
static assets. No server-side runtime is required on the host: the VPS
serves files only. Provenance stays first-class: the site shows sources,
hashes and interpretation flags, not just rankings.
"""

from __future__ import annotations

import html
import json
import shutil
import string
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psd2_kpi_es import config, queries
from psd2_kpi_es.catalog import load_catalog

TEMPLATE = config.SITE_DIR / "templates" / "base.html"
STATIC = config.SITE_DIR / "static"
DEFAULT_OUT = config.SITE_DIR / "dist"

REPO_URL = "https://github.com/Huntsman1756/psd2-kpi-es"

NAV_PAGES = [
    ("index.html", "Overview"),
    ("entities.html", "Entities"),
    ("compare.html", "Compare"),
    ("history.html", "History"),
    ("provenance.html", "Provenance"),
]


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _fmt_value(v: float | None, unit: str | None) -> str:
    if v is None:
        return "—"
    if unit == "percent":
        return f"{v:.3f}".rstrip("0").rstrip(".") + " %"
    if unit == "ms":
        return f"{v:,.1f} ms"
    if unit == "seconds":
        return f"{v:.3f} s"
    if unit == "count":
        return f"{v:,.0f}"
    return str(v)


def _table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    """Build an HTML table. `headers` are escaped; `rows` cells are trusted
    markup — callers must escape dynamic text themselves."""
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    c = f' class="{cls}"' if cls else ""
    return f"<table{c}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _render_page(page: str, title: str, content: str, generated: str) -> str:
    tpl = string.Template(TEMPLATE.read_text(encoding="utf-8"))
    return tpl.substitute(
        page=page, title=title, content=content, generated=generated, repo=REPO_URL
    )


# ------------------------------------------------------------------ data ----


def _collect() -> dict[str, Any]:
    cov = queries.coverage_rows()
    catalog = load_catalog()
    entities = [
        {"id": eid, "brand": ent.brand_name, "legal": ent.legal_name}
        for eid, (ent, _srcs) in sorted(catalog.items())
    ]
    periods = {
        t: [
            r["period_label"]
            for r in queries.cols(
                "SELECT DISTINCT period_label FROM observations WHERE period_type=? ORDER BY 1",
                [t],
            )
        ]
        for t in ("quarter", "month")
    }
    combos = queries.cols(
        "SELECT DISTINCT metric, service, interface_type FROM observations "
        "WHERE value_status='reported' ORDER BY 1, 2, 3"
    )
    return {
        "coverage": cov,
        "entities": entities,
        "periods": periods,
        "combos": combos,
        "totals": {
            "entities": len(entities),
            "observations": sum(r["observations"] for r in cov),
            "artifacts": queries.cols("SELECT count(*) AS n FROM sources")[0]["n"],
            "earliest": str(min(r["earliest"] for r in cov)),
            "latest": str(max(r["latest"] for r in cov)),
        },
        "metrics": sorted({c["metric"] for c in combos}),
        "services": sorted({c["service"] for c in combos}),
        "interfaces": sorted({c["interface_type"] for c in combos}),
    }


def _compare_rows(periods: list[str], combos: list[dict]) -> list[dict]:
    """Precompute compare_rows() for every period x metric x service x
    interface combination so the site needs no query layer."""
    out = []
    for p in periods:
        for c in combos:
            for r in queries.compare_rows(p, c["metric"], c["service"], c["interface_type"]):
                out.append(
                    {
                        "period": p,
                        "metric": c["metric"],
                        "service": c["service"],
                        "interface": c["interface_type"],
                        "entity_id": r["entity_id"],
                        "value": r["value"],
                        "unit": r["unit"],
                        "aggregation": r["aggregation"],
                        "comparability_group": r["comparability_group"],
                        "n_days": r["n_days"],
                    }
                )
    return out


def _history_file(entity_id: str) -> dict:
    """All reported series for an entity, grouped by metric -> series."""
    rows = queries.cols(
        """
        SELECT metric, service, interface_type, period_type, period_start,
               period_label, value, unit, comparability_group, interpretation
        FROM observations
        WHERE entity_id=? AND value_status='reported'
        ORDER BY period_start
        """,
        [entity_id],
    )
    series: dict[tuple, dict] = {}
    for r in rows:
        key = (r["metric"], r["service"], r["interface_type"], r["period_type"])
        s = series.setdefault(
            key,
            {
                "metric": r["metric"],
                "service": r["service"],
                "interface": r["interface_type"],
                "period_type": r["period_type"],
                "unit": r["unit"],
                "comparability_group": r["comparability_group"],
                "inferred": 0,
                "points": [],
            },
        )
        s["points"].append([str(r["period_start"]), r["value"], r["period_label"]])
        if r["interpretation"] == "inferred":
            s["inferred"] += 1
    metrics: dict[str, list[dict]] = {}
    for s in series.values():
        metrics.setdefault(s["metric"], []).append(s)
    return {"entity": entity_id, "metrics": metrics}


# ----------------------------------------------------------------- pages ----


def _index_page(data: dict[str, Any]) -> str:
    t = data["totals"]
    latest_q = data["periods"]["quarter"][-1]
    cmp_rows = queries.compare_rows(latest_q, "availability", "ALL", "dedicated_api")
    table = _table(
        ["Entity", "Availability", "Basis", "Days", "Comparability"],
        [
            [
                f'<a href="entity-{_esc(r["entity_id"])}.html">{_esc(r["entity_id"])}</a>',
                _fmt_value(r["value"], r["unit"]),
                _esc(r["aggregation"]),
                _esc(r["n_days"]),
                f"<code>{_esc(r['comparability_group'])}</code>",
            ]
            for r in cmp_rows
        ],
    )
    gaps = queries.gaps_rows()
    gaps_html = _table(
        ["Entity", "Missing quarter"],
        [[_esc(r["entity_id"]), _esc(r["missing_period"])] for r in gaps],
    )
    quirks = _quirks_section()
    return f"""
<section class="hero">
  <h1>PSD2 KPI Spain</h1>
  <p class="lede">Availability and performance statistics that Spanish ASPSPs
  self-publish under Art. 32(4) of Delegated Regulation (EU) 2018/389 —
  normalized into one auditable dataset with row-level provenance.</p>
  <div class="stats">
    <div><strong>{t["entities"]}</strong><span>ASPSPs</span></div>
    <div><strong>{t["artifacts"]}</strong><span>source artifacts</span></div>
    <div><strong>{t["observations"]:,}</strong><span>observations</span></div>
    <div><strong>{_esc(t["earliest"])} → {_esc(t["latest"])}</strong><span>coverage</span></div>
  </div>
</section>

<h2>Latest reported quarter — dedicated API availability ({_esc(latest_q)})</h2>
{table}
<p class="muted">Derived from daily published values; entities that publish
only a period aggregate are marked <code>published_aggregate</code>.</p>

<h2>Coverage gaps</h2>
<p>Fully-ended quarters with no data found in the configured sources.
Facts, not compliance verdicts.</p>
{gaps_html}

{quirks}
"""


def _quirks_section() -> str:
    n_inferred = queries.cols(
        "SELECT count(*) AS n FROM observations WHERE interpretation='inferred'"
    )[0]["n"]
    neg = queries.cols(
        "SELECT entity_id, period_label, value, raw_value FROM observations "
        "WHERE metric='availability' AND value<0 ORDER BY period_label"
    )
    dual = queries.cols(
        "SELECT period_hint, count(*) AS n FROM sources "
        "WHERE entity_id='caixabank' AND period_hint IS NOT NULL "
        "GROUP BY period_hint HAVING count(*)>1 ORDER BY 1"
    )
    neg_rows = "".join(
        f"<li><strong>{_esc(r['entity_id'])}</strong> {_esc(r['period_label'])}: "
        f"published <code>{_esc(r['raw_value'])}</code> — kept verbatim, flagged "
        f"as a range warning.</li>"
        for r in neg
    )
    dual_txt = ""
    if dual:
        hints = ", ".join(_esc(d["period_hint"]) for d in dual)
        dual_txt = (
            f"<li><strong>CaixaBank</strong> publishes {hints} twice (XLSX + PDF). "
            "The pipeline keeps one per logical key and reports precision conflicts.</li>"
        )
    return f"""
<h2>Source quirks preserved, not corrected</h2>
<ul class="quirks">
  <li><strong>Santander</strong> labels a column <code>Rendimiento (s)</code>
  whose magnitudes are milliseconds. {n_inferred:,} observations carry
  <code>interpretation=inferred</code> with the raw unit preserved.</li>
  {neg_rows}
  {dual_txt}
</ul>
<p class="caveat">All figures are self-reported by each entity; definitions
differ subtly. Rows carry a comparability group and <code>rank
--comparable-only</code> refuses to mix them.</p>
"""


def _entities_page(data: dict[str, Any]) -> str:
    rows = []
    name = {e["id"]: e["brand"] for e in data["entities"]}
    for r in data["coverage"]:
        eid = r["entity_id"]
        rows.append(
            [
                f'<a href="entity-{_esc(eid)}.html">{_esc(name.get(eid, eid))}</a>',
                _esc(r["days"]),
                _esc(r["quarters"]),
                _esc(r["earliest"]),
                _esc(r["latest"]),
                _esc(r["observations"]),
            ]
        )
    return "<h1>Entities</h1>" + _table(
        ["Entity", "Days", "Quarters", "Earliest", "Latest", "Observations"], rows
    )


def _entity_page(entity: dict, coverage: dict, generated: str) -> str:
    eid = entity["id"]
    latest = [r for r in queries.latest_rows() if r["entity_id"] == eid]
    latest_table = _table(
        ["Period", "Metric", "Service", "Interface", "Value"],
        [
            [
                _esc(r["period_label"]),
                _esc(r["metric"]),
                _esc(r["service"]),
                _esc(r["interface_type"]),
                _fmt_value(r["value"], r["unit"]),
            ]
            for r in latest[:40]
        ],
    )
    sources = queries.sources_rows(eid)
    src_table = _table(
        ["Period", "File", "Retrieved", "SHA-256"],
        [
            [
                _esc(s["period_hint"]),
                f'<a href="{_esc(s["source_url"])}">{_esc(s["filename"] or s["source_url"])}</a>',
                _esc(str(s["retrieved_at"])[:10]),
                f'<code title="{_esc(s["sha256"])}">{_esc(s["sha256"][:12])}…</code>',
            ]
            for s in sources
        ],
    )
    return f"""
<h1>{_esc(entity["brand"])}</h1>
<p class="muted">{_esc(entity["legal"])}</p>
<div class="stats small">
  <div><strong>{coverage["days"]:,}</strong><span>days reported</span></div>
  <div><strong>{coverage["quarters"]}</strong><span>quarters</span></div>
  <div><strong>{_esc(coverage["earliest"])} → {_esc(coverage["latest"])}</strong>
  <span>coverage</span></div>
  <div><strong>{coverage["observations"]:,}</strong><span>observations</span></div>
</div>
<h2>Availability history</h2>
<div class="chart" id="entity-chart" data-entity="{_esc(eid)}"></div>
<p class="muted" id="entity-chart-info"></p>
<h2>Latest reported values</h2>
{latest_table}
<h2>Source artifacts ({len(sources)})</h2>
{src_table}
"""


def _compare_page() -> str:
    return """
<h1>Compare</h1>
<p>Cross-entity comparison for a period. Rows are grouped by
<code>comparability_group</code> — methodologies that are not aligned are
shown separately instead of being mixed into one ranking.</p>
<div class="controls">
  <label>Period <select id="sel-period"></select></label>
  <label>Metric <select id="sel-metric"></select></label>
  <label>Service <select id="sel-service"></select></label>
  <label>Interface <select id="sel-iface"></select></label>
  <label class="chk"><input type="checkbox" id="chk-all"> show all groups</label>
</div>
<div id="compare-out"></div>
"""


def _history_page() -> str:
    return """
<h1>History</h1>
<div class="controls">
  <label>Entity <select id="sel-entity"></select></label>
  <label>Metric <select id="sel-metric"></select></label>
  <label>Granularity <select id="sel-gran"></select></label>
</div>
<div class="chart" id="chart"></div>
<p class="muted" id="history-info"></p>
"""


def _explain_block(row: dict, caption: str) -> str:
    fields = [
        ("entity", row["entity_name"]),
        ("period", row["period_label"]),
        ("interface / service", f"{row['interface_type']} / {row['service']}"),
        ("metric", row["metric"]),
        ("value", _fmt_value(row["value"], row["unit"])),
        ("raw cell", f"{row['raw_label']} = {row['raw_value']}"),
        ("raw unit", row["raw_unit"]),
        ("interpretation", row["interpretation"]),
        ("source", f"{row['filename']} — {row['source_url']}"),
        ("sha256", row["source_sha256"]),
        ("parser", f"{row['parser_name']}:{row['parser_version']}"),
        ("locator", row["source_document"]),
        ("notes", row["notes"]),
    ]
    dl = "".join(
        f"<dt>{_esc(k)}</dt><dd>{_esc(v) if v is not None else '—'}</dd>" for k, v in fields
    )
    return f'<h3>{_esc(caption)}</h3><dl class="explain">{dl}</dl>'


def _provenance_page() -> str:
    examples = ""
    anomaly = queries.cols(
        "SELECT observation_id FROM observations WHERE metric='availability' AND value<0 LIMIT 1"
    )
    if anomaly:
        row = queries.explain_row(anomaly[0]["observation_id"])
        if row:
            examples += _explain_block(row, "Published anomaly kept verbatim")
    inferred = queries.cols(
        "SELECT observation_id FROM observations WHERE interpretation='inferred' LIMIT 1"
    )
    if inferred:
        row = queries.explain_row(inferred[0]["observation_id"])
        if row:
            examples += _explain_block(row, "Documented interpretation (unit relabelled)")
    sources = queries.cols("SELECT * FROM sources ORDER BY entity_id, retrieved_at")
    src_table = _table(
        ["Entity", "Period", "File", "Retrieved", "SHA-256"],
        [
            [
                _esc(s["entity_id"]),
                _esc(s["period_hint"]),
                f'<a href="{_esc(s["source_url"])}">{_esc(s["filename"] or s["source_url"])}</a>',
                _esc(str(s["retrieved_at"])[:10]),
                f'<code title="{_esc(s["sha256"])}">{_esc(s["sha256"][:12])}…</code>',
            ]
            for s in sources
        ],
    )
    return f"""
<h1>Provenance</h1>
<p>Every normalized value traces back to the exact document, cell text,
content hash and parser version that produced it:</p>
<pre class="chain">entity → period → document → page/cell → raw value
       → transformation → parser@version → sha256 → normalized row</pre>
{examples}
<h2>All source artifacts ({len(sources)})</h2>
<p>Raw documents are not redistributed; re-fetch each URL and verify the
SHA-256. Publishers may mutate or remove files — historical rebuilds are
not guaranteed.</p>
{src_table}
"""


# ----------------------------------------------------------------- build ----


def _write_json(out: Path, name: str, payload: Any) -> None:
    (out / "data" / name).write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        encoding="utf-8",
    )


def build(out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    shutil.copytree(STATIC, out / "static")

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    data = _collect()
    periods = data["periods"]["quarter"] + data["periods"]["month"]

    _write_json(
        out,
        "meta.json",
        {
            "generated": generated,
            "totals": data["totals"],
            "quarters": data["periods"]["quarter"],
            "months": data["periods"]["month"],
            "entities": data["entities"],
            "metrics": data["metrics"],
            "services": data["services"],
            "interfaces": data["interfaces"],
        },
    )
    _write_json(out, "compare.json", _compare_rows(periods, data["combos"]))

    cov_by_entity = {r["entity_id"]: r for r in data["coverage"]}
    pages = {
        "index.html": _render_page("index", "Overview", _index_page(data), generated),
        "entities.html": _render_page("entities", "Entities", _entities_page(data), generated),
        "compare.html": _render_page("compare", "Compare", _compare_page(), generated),
        "history.html": _render_page("history", "History", _history_page(), generated),
        "provenance.html": _render_page("provenance", "Provenance", _provenance_page(), generated),
    }
    for e in data["entities"]:
        _write_json(out, f"history-{e['id']}.json", _history_file(e["id"]))
        pages[f"entity-{e['id']}.html"] = _render_page(
            "entity",
            e["brand"],
            _entity_page(e, cov_by_entity[e["id"]], generated),
            generated,
        )
    for name, content in pages.items():
        (out / name).write_text(content, encoding="utf-8")
    return out
