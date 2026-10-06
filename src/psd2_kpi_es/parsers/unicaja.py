"""Unicaja Banco PSD2 statistics parser.

Source: quarterly PDFs 'psd2-estadisticas-unicaja-del-<n>T<yyyy>.pdf' (plus two
date-range named files for the initial periods) linked from
https://www.unicajabanco.es/es/legales/tablon-de-anuncios

Layout (verified against 3T2025): cover page, then per-month pages alternating
'Indicadores Disponibilidad <Mes> <Año>' and 'Indicadores Rendimiento
<Mes> <Año>', each a daily table; last page contains KPI definitions.

Extraction is positional: header words ('APIs' / 'Canales Online') define
column anchors; each data word is assigned to its nearest anchor. This avoids
regex fragility when pdfminer merges 'ms'/'%' glyphs into numbers.

Columns:
  Disponibilidad: date | actividad APIs | Canales | inactividad APIs | Canales (%)
  Rendimiento:    date | TMR {PIS,AIS,PIISP} APIs | Canales | err APIs | Canales

'Canales Online (Web, App)' aggregates web+mobile -> psu_interface.
'-' cells mean not reported and are skipped with no observation.
"""

from __future__ import annotations

import io
import re
from datetime import date

import pdfplumber

from psd2_kpi_es.models import (
    Aggregation,
    Comparability,
    Entity,
    InterfaceType,
    Metric,
    Observation,
    ParseResult,
    ParseWarning,
    PeriodType,
    Service,
    SourceArtifact,
    Unit,
)
from psd2_kpi_es.parsers.textnorm import parse_es_date, parse_es_percent

NAME = "unicaja"
VERSION = "unicaja:2"

_INDEX_LINK_RE = re.compile(r"[^\"'\s]*psd2-estadisticas-unicaja[^\"'\s]*\.pdf", re.IGNORECASE)
_URL_Q_RE = re.compile(r"-del-([1-4])T(\d{4})\.pdf", re.IGNORECASE)
_HEADER_RE = re.compile(
    r"Indicadores\s+(Disponibilidad|Rendimiento)\s+(\w+)\s+(\d{4})", re.IGNORECASE
)
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_ROW_MERGE_TOL = 4.0  # pdf splits one table row across adjacent 'top' values

_SERVICE_TMR = [Service.PIS, Service.AIS, Service.PIISP]

# 2019 legacy layout: monthly KPI aggregates (no daily rows)
_MONTH_HDR_RE = re.compile(
    r"Indicadores\s+(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|"
    r"Octubre|Noviembre|Diciembre)\s+(\d{4})(?:\s*\(desde\s+(\d{2}/\d{2}/\d{4})\))?",
    re.IGNORECASE,
)
_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_KPI_ROW_RE = re.compile(
    r"(Tiempo diario de actividad|Tiempo diario de inactividad|"
    r"Tiempo medio diario (PIS|AIS|PIISP)|Tasa diaria de respuestas err.neas)\s+(.*)$",
    re.IGNORECASE,
)
_VAL_TOK_RE = re.compile(r"-?[\d.,]+\s*(?:%|ms)|-|NP", re.IGNORECASE)


def discover_links(index_html: bytes) -> list[str]:
    text = index_html.decode("utf-8", errors="replace")
    urls = set()
    for m in _INDEX_LINK_RE.findall(text):
        if m.startswith("http"):
            urls.add(m)
        elif m.startswith("/"):
            urls.add("https://www.unicajabanco.es" + m)
    return sorted(urls)


def period_hint(url: str) -> str | None:
    m = _URL_Q_RE.search(url)
    if m:
        return f"{m.group(2)}Q{int(m.group(1))}"
    return None


def _obs(
    *,
    entity: Entity,
    artifact: SourceArtifact,
    day: date,
    interface: InterfaceType,
    service: Service,
    metric: Metric,
    value: float,
    unit: Unit,
    comparability_group: str,
    raw_label: str,
    raw_value: str,
    raw_unit: str | None,
    locator: str,
    metric_definition: str | None = None,
) -> Observation:
    return Observation(
        entity_id=entity.entity_id,
        entity_name=entity.legal_name,
        period_start=day,
        period_end=day,
        period_type=PeriodType.DAY,
        period_label=day.isoformat(),
        interface_type=interface,
        service=service,
        metric=metric,
        value=value,
        unit=unit,
        aggregation=Aggregation.DAILY_MEAN
        if metric in (Metric.RESPONSE_TIME, Metric.ERROR_RATE)
        else Aggregation.POINT,
        metric_definition=metric_definition,
        comparability=Comparability.PARTIAL,
        comparability_group=comparability_group,
        source_id=artifact.source_id,
        source_url=artifact.source_url,
        source_document=locator,
        retrieved_at=artifact.retrieved_at,
        source_sha256=artifact.sha256,
        parser_name=NAME,
        parser_version=VERSION,
        raw_label=raw_label,
        raw_value=raw_value,
        raw_unit=raw_unit,
    )


def _group_rows(words: list[dict]) -> list[list[dict]]:
    """Group words into visual rows by 'top' proximity."""
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    rows: list[list[dict]] = []
    for w in words:
        if rows and abs(w["top"] - rows[-1][-1]["top"]) <= _ROW_MERGE_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def _column_anchors(rows: list[list[dict]]) -> list[float] | None:
    """Find column x-centers from the header line containing 'APIs'."""
    for row in rows:
        texts = [w["text"] for w in row]
        if "APIs" not in texts:
            continue
        anchors: list[float] = []
        for w in row:
            if w["text"] in ("APIs", "Canales"):
                anchors.append((w["x0"] + w["x1"]) / 2)
            # 'Online', '(Web,', 'App)', 'PSD2' extend/ignore
        if anchors:
            return anchors
    return None


def _cell_values(row: list[dict], anchors: list[float]) -> tuple[date | None, list[str]]:
    """Assign each word in a data row to the nearest column anchor."""
    day = None
    cells: list[list[str]] = [[] for _ in anchors]
    for w in row:
        if _DATE_RE.match(w["text"]):
            day = date.fromisoformat(parse_es_date(w["text"]))
            continue
        c = (w["x0"] + w["x1"]) / 2
        idx = min(range(len(anchors)), key=lambda i: abs(c - anchors[i]))
        cells[idx].append(w["text"])
    return day, ["".join(c) for c in cells]


def _recover(tok: str) -> str:
    """Recover a numeric token polluted by overlapping unit glyphs.

    pdfminer sometimes merges the 'ms'/'%' cell suffix into the digits
    ('ms13831383ms', '137m0sms', '%0%'). Cleaning: remove letters and stray
    '%'/',', then, if the remaining string is an even-length duplication
    ('13831383'), keep one half. Anything still unparseable is left for the
    caller to reject loudly.
    """
    t = re.sub(r"[a-zA-Z]", "", tok)
    t = t.replace("%", "").rstrip(",.").strip()
    n = len(t)
    if n >= 4 and n % 2 == 0 and t[: n // 2] == t[n // 2 :]:
        t = t[: n // 2]
    return t


def _pct(tok: str) -> float:
    return parse_es_percent(_recover(tok) + "%")


def _ms(tok: str) -> float:
    return parse_es_percent(_recover(tok) + "%")


def parse(artifact: SourceArtifact, content: bytes, entity: Entity) -> ParseResult:
    warnings: list[ParseWarning] = []
    out: list[Observation] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages = list(pdf.pages)

    kpi_def = None
    for p in pages:
        t = p.extract_text() or ""
        if "Indicadores Claves" in t or "Definición de los Indicadores" in t:
            kpi_def = "KPI definitions included in the source document (last page)."

    seen_days: set[date] = set()
    for page_no, page in enumerate(pages):
        text = page.extract_text() or ""
        hdr = _HEADER_RE.search(text)
        if not hdr:
            continue
        section = hdr.group(1).lower()
        locator = f"page {page_no}: {hdr.group(2)} {hdr.group(3)}"

        words = page.extract_words(x_tolerance=1.5)
        rows = _group_rows(words)
        anchors = _column_anchors(rows)
        if not anchors:
            warnings.append(
                ParseWarning(code="NO_ANCHORS", message=f"page {page_no}: no column header")
            )
            continue
        expected = 4 if section == "disponibilidad" else 8
        if len(anchors) != expected:
            warnings.append(
                ParseWarning(
                    code="ANCHOR_COUNT",
                    message=f"page {page_no}: {len(anchors)} anchors, expected {expected}",
                )
            )
            continue

        for row in rows:
            day, cells = _cell_values(row, anchors)
            if day is None:
                continue
            seen_days.add(day)
            cells = [c for c in cells]

            if section == "disponibilidad":
                for i, iface in enumerate(
                    (InterfaceType.DEDICATED_API, InterfaceType.PSU_INTERFACE)
                ):
                    for j, (metric, raw_label, group) in enumerate(
                        (
                            (
                                Metric.AVAILABILITY,
                                "Tiempo diario actividad",
                                "availability_daily_pct",
                            ),
                            (Metric.DOWNTIME, "Tiempo diario inactividad", "downtime_daily_pct"),
                        )
                    ):
                        tok = cells[i + j * 2]
                        if not tok or tok == "-":
                            continue
                        try:
                            val = _pct(tok)
                        except ValueError:
                            warnings.append(ParseWarning(code="CELL", message=f"{day} {tok!r}"))
                            continue
                        out.append(
                            _obs(
                                entity=entity,
                                artifact=artifact,
                                day=day,
                                interface=iface,
                                service=Service.ALL,
                                metric=metric,
                                value=val,
                                unit=Unit.PERCENT,
                                comparability_group=group,
                                raw_label=raw_label,
                                raw_value=tok,
                                raw_unit="%",
                                locator=locator,
                            )
                        )
            else:  # rendimiento
                for svc_i, service in enumerate(_SERVICE_TMR):
                    for j, iface in enumerate(
                        (InterfaceType.DEDICATED_API, InterfaceType.PSU_INTERFACE)
                    ):
                        tok = cells[svc_i * 2 + j]
                        if not tok or tok == "-":
                            continue
                        try:
                            val = _ms(tok)
                        except ValueError:
                            warnings.append(ParseWarning(code="CELL", message=f"{day} {tok!r}"))
                            continue
                        out.append(
                            _obs(
                                entity=entity,
                                artifact=artifact,
                                day=day,
                                interface=iface,
                                service=service,
                                metric=Metric.RESPONSE_TIME,
                                value=val,
                                unit=Unit.MS,
                                comparability_group="response_time_daily_mean_ms",
                                raw_label=f"Tiempo medio diario {service.value}",
                                raw_value=tok,
                                raw_unit="ms",
                                locator=locator,
                                metric_definition=kpi_def,
                            )
                        )
                for j, iface in enumerate(
                    (InterfaceType.DEDICATED_API, InterfaceType.PSU_INTERFACE)
                ):
                    tok = cells[6 + j]
                    if not tok or tok == "-":
                        continue
                    try:
                        val = _pct(tok)
                    except ValueError:
                        warnings.append(ParseWarning(code="CELL", message=f"{day} {tok!r}"))
                        continue
                    out.append(
                        _obs(
                            entity=entity,
                            artifact=artifact,
                            day=day,
                            interface=iface,
                            service=Service.ALL,
                            metric=Metric.ERROR_RATE,
                            value=val,
                            unit=Unit.PERCENT,
                            comparability_group="error_rate_daily_pct",
                            raw_label="Tasa diaria resp. Erróneas",
                            raw_value=tok,
                            raw_unit="%",
                            locator=locator,
                        )
                    )

    if not seen_days:
        # legacy monthly-aggregate layout (2019 report)
        out, month_warns = _parse_monthly(artifact, pages, entity)
        warnings.extend(month_warns)
        if not out:
            warnings.append(
                ParseWarning(code="NO_OBS", message="no daily or monthly rows extracted")
            )
    return ParseResult(observations=out, warnings=warnings)


def _parse_monthly(artifact: SourceArtifact, pages, entity: Entity):
    """Legacy 2019 layout: 'Indicadores <Mes> <Año>' sections, KPI rows with
    'APIs PSD2' and 'Canales Online' columns -> monthly observations."""
    import calendar

    warnings: list[ParseWarning] = []
    out: list[Observation] = []
    cur_start: date | None = None
    cur_end: date | None = None
    locator = "monthly indicators"

    for page_no, page in enumerate(pages):
        for line in (page.extract_text() or "").splitlines():
            hdr = _MONTH_HDR_RE.search(line)
            if hdr:
                month = _MONTHS[hdr.group(1).lower()]
                year = int(hdr.group(2))
                cur_start = date(year, month, 1)
                if hdr.group(3):
                    cur_start = date.fromisoformat(parse_es_date(hdr.group(3)))
                cur_end = date(year, month, calendar.monthrange(year, month)[1])
                locator = f"page {page_no}: {hdr.group(1)} {year}"
                continue
            m = _KPI_ROW_RE.search(line.strip())
            if not m or cur_start is None or cur_end is None:
                continue
            label = m.group(1)
            service = _SERVICE_MAP_LBL.get(label.lower(), Service.ALL)
            toks = _VAL_TOK_RE.findall(m.group(3))
            if len(toks) != 2:
                warnings.append(
                    ParseWarning(code="MROW", message=f"{cur_start} {label!r}: {m.group(3)!r}")
                )
                continue
            if "actividad" in label and "inactividad" not in label:
                metric, unit, group = Metric.AVAILABILITY, Unit.PERCENT, "availability_daily_pct"
            elif "inactividad" in label:
                metric, unit, group = Metric.DOWNTIME, Unit.PERCENT, "downtime_daily_pct"
            elif "medio diario" in label:
                metric, unit, group = Metric.RESPONSE_TIME, Unit.MS, "response_time_daily_mean_ms"
            else:
                metric, unit, group = Metric.ERROR_RATE, Unit.PERCENT, "error_rate_daily_pct"

            for j, iface in enumerate((InterfaceType.DEDICATED_API, InterfaceType.PSU_INTERFACE)):
                tok = toks[j]
                if tok.strip() in ("-", "NP"):
                    continue
                try:
                    val = _pct(tok) if unit is Unit.PERCENT else _ms(tok)
                except ValueError:
                    warnings.append(ParseWarning(code="CELL", message=f"{cur_start} {tok!r}"))
                    continue
                o = Observation(
                    entity_id=entity.entity_id,
                    entity_name=entity.legal_name,
                    period_start=cur_start,
                    period_end=cur_end,
                    period_type=PeriodType.MONTH,
                    period_label=f"{cur_start.year:04d}-{cur_start.month:02d}",
                    interface_type=iface,
                    service=service,
                    metric=metric,
                    value=val,
                    unit=unit,
                    aggregation=Aggregation.MEAN,
                    comparability=Comparability.PARTIAL,
                    comparability_group=group,
                    source_id=artifact.source_id,
                    source_url=artifact.source_url,
                    source_document=locator,
                    retrieved_at=artifact.retrieved_at,
                    source_sha256=artifact.sha256,
                    parser_name=NAME,
                    parser_version=VERSION,
                    raw_label=label,
                    raw_value=tok,
                    raw_unit="%" if unit is Unit.PERCENT else "ms",
                )
                out.append(o)
    return out, warnings


_SERVICE_MAP_LBL = {
    "tiempo medio diario pis": Service.PIS,
    "tiempo medio diario ais": Service.AIS,
    "tiempo medio diario piisp": Service.PIISP,
}


name = NAME
version = VERSION
