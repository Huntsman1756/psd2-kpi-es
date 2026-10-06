"""Renta 4 Banco PSD2 statistics parser.

Source: quarterly PDFs 'PublicacionEstadisticasRenta4_PSD2_<n>T<yy>.pdf' linked
from https://www.r4.com/normativa/normativa-psd2.

Layout (verified against 2T2024 sample):
  page 0        'Resumen': quarterly aggregates per service (Total/PIS/AIS/FCS/
                PCOMUNES) for INTERFAZ APIs and INTERFAZ DIGITAL side by side.
  pages 1..n    daily tables per ASPSP_<service> section, digital table on the
                left, APIs table on the right; extract_text() merges both
                halves on the same line.

Only rows whose operation is 'Total' are extracted (per-operation rows are
kept in the raw artifact but not normalized in v0.1).

Column semantics (documented in the PDF itself):
  Peticiones OK / KO      request counts ('NP' = not published)
  TMD                     daily mean response time, ms
  TDRE                    daily error response rate, %
  TDA                     daily availability ('tiempo diario de actividad'), %
  OBJETIVO TDA            service level target for TDA (only in Resumen)
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
    ValueStatus,
)
from psd2_kpi_es.parsers.base import quarter_bounds
from psd2_kpi_es.parsers.textnorm import parse_es_date, parse_es_number, parse_es_percent

NAME = "renta4"
VERSION = "renta4:1"

_INDEX_LINK_RE = re.compile(
    r"https?://[^\"'\s]*PublicacionEstadisticasRenta4_PSD2[^\"'\s]*\.pdf", re.IGNORECASE
)
_URL_PERIOD_RE = re.compile(r"_([1-4])T(\d{2})\.pdf$", re.IGNORECASE)
_DATE_ROW_RE = re.compile(r"(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(\d{2}/\d{2}/\d{2})\s+(.+)$")
_SERVICE_HDR_RE = re.compile(r"ASPSP_(PIS|AIS|FCS|COMUNES)\b")
_PERIOD_RE = re.compile(r"Per[ií]odo:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
_SUMMARY_ROW_RE = re.compile(r"\b(Total|PIS|AIS|FCS|PCOMUNES)\b")
_NUM_TOK_RE = re.compile(r"NP|-?[\d.,]+%?")

_SERVICE_MAP = {
    "PIS": Service.PIS,
    "AIS": Service.AIS,
    "FCS": Service.PIISP,
    "PCOMUNES": Service.UNKNOWN,
    "Total": Service.ALL,
}
_SECTION_SERVICE = {"PIS": "PIS", "AIS": "AIS", "FCS": "FCS", "COMUNES": "PCOMUNES"}


def discover_links(index_html: bytes) -> list[str]:
    text = index_html.decode("utf-8", errors="replace")
    return sorted(set(_INDEX_LINK_RE.findall(text)))


def period_hint(url: str) -> str | None:
    m = _URL_PERIOD_RE.search(url)
    if m:
        return f"20{int(m.group(2)):02d}Q{int(m.group(1))}"
    if url.rstrip("/").endswith("PublicacionEstadisticasRenta4_PSD2.pdf"):
        return "2019Q4"  # first publication, per the index page label
    return None


def _obs(
    *,
    entity: Entity,
    artifact: SourceArtifact,
    period_start: date,
    period_end: date,
    period_type: PeriodType,
    period_label: str,
    interface: InterfaceType,
    service: Service,
    metric: Metric,
    value: float | None,
    unit: Unit,
    aggregation: Aggregation,
    value_status: ValueStatus = ValueStatus.REPORTED,
    comparability_group: str,
    raw_label: str,
    raw_value: str | None,
    raw_unit: str | None,
    locator: str,
    notes: str | None = None,
) -> Observation:
    return Observation(
        entity_id=entity.entity_id,
        entity_name=entity.legal_name,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        period_label=period_label,
        interface_type=interface,
        service=service,
        metric=metric,
        value=value,
        unit=unit,
        aggregation=aggregation,
        value_status=value_status,
        metric_definition=None,
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
        notes=notes,
    )


def _is_pct(tok: str) -> bool:
    return tok.endswith("%")


def _num(tok: str) -> float:
    return parse_es_percent(tok) if _is_pct(tok) else parse_es_number(tok)


def _emit_metrics(
    out: list[Observation],
    *,
    entity: Entity,
    artifact: SourceArtifact,
    date_or_period: tuple[date, date, PeriodType, str],
    interface: InterfaceType,
    service: Service,
    tokens: list[str],
    locator: str,
    is_summary: bool,
    warnings: list[ParseWarning],
) -> None:
    """Map a token list to metric observations.

    APIs half:    OK KO TMD [TDRE] TDA [OBJETIVO]
    Digital half: NP NP TMD [TDRE] TDA [OBJETIVO]
    TDA and OBJETIVO are percent tokens; TDRE is percent or bare '0'.
    """
    start, end, ptype, plabel = date_or_period
    toks = list(tokens)

    counts: list[tuple[str, str]] = []  # (raw_label, raw_value)
    if toks and toks[0] == "NP":
        # digital interface: counts not published
        toks = toks[2:] if len(toks) >= 2 and toks[1] == "NP" else toks[1:]
    elif len(toks) >= 2:
        counts = [("Peticiones OK", toks[0]), ("Peticiones KO", toks[1])]
        toks = toks[2:]

    objetivo: str | None = None
    if is_summary and toks:
        objetivo = toks.pop()

    tda = toks.pop() if toks else None
    tmd = toks.pop(0) if toks else None
    tdre = toks.pop(0) if toks else None

    def kw(**kw):
        return dict(
            entity=entity,
            artifact=artifact,
            period_start=start,
            period_end=end,
            period_type=ptype,
            period_label=plabel,
            interface=interface,
            service=service,
            locator=locator,
        )

    agg = Aggregation.MEAN if is_summary else Aggregation.DAILY_MEAN
    for raw_label, raw_val in counts:
        out.append(
            _obs(
                **kw(),
                metric=Metric.REQUEST_COUNT,
                value=_num(raw_val),
                unit=Unit.COUNT,
                aggregation=Aggregation.SUM,
                comparability_group="request_count_daily",
                raw_label=raw_label,
                raw_value=raw_val,
                raw_unit=None,
            )
        )
    if tmd is not None and tmd != "NP":
        out.append(
            _obs(
                **kw(),
                metric=Metric.RESPONSE_TIME,
                value=_num(tmd),
                unit=Unit.MS,
                aggregation=agg,
                comparability_group="response_time_daily_mean_ms",
                raw_label="TMD (diario, ms)",
                raw_value=tmd,
                raw_unit="ms",
            )
        )
    if tdre is not None:
        raw_tdre = tdre if _is_pct(tdre) else tdre + "%"
        out.append(
            _obs(
                **kw(),
                metric=Metric.ERROR_RATE,
                value=_num(raw_tdre),
                unit=Unit.PERCENT,
                aggregation=agg,
                comparability_group="error_rate_daily_pct",
                raw_label="TDRE (diario, %)",
                raw_value=raw_tdre,
                raw_unit="%",
            )
        )
    if tda is not None:
        out.append(
            _obs(
                **kw(),
                metric=Metric.AVAILABILITY,
                value=_num(tda),
                unit=Unit.PERCENT,
                aggregation=Aggregation.MEAN if is_summary else Aggregation.POINT,
                comparability_group="availability_daily_pct",
                raw_label="TDA (diario, %)",
                raw_value=tda,
                raw_unit="%",
            )
        )
    if objetivo is not None:
        out.append(
            _obs(
                **kw(),
                metric=Metric.OTHER,
                value=_num(objetivo),
                unit=Unit.PERCENT,
                aggregation=Aggregation.POINT,
                comparability_group="sla_target_pct",
                raw_label="OBJETIVO TDA",
                raw_value=objetivo,
                raw_unit="%",
                notes="Service level target published by the ASPSP, not a measured value.",
            )
        )


def parse(artifact: SourceArtifact, content: bytes, entity: Entity) -> ParseResult:
    warnings: list[ParseWarning] = []
    out: list[Observation] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        pages_text = [(p.extract_text() or "") for p in pdf.pages]

    if not pages_text:
        warnings.append(ParseWarning(code="EMPTY_PDF", message="no pages extracted"))
        return ParseResult(warnings=warnings)

    # --- quarter period from page 0 ---
    m = _PERIOD_RE.search(pages_text[0])
    if not m:
        warnings.append(
            ParseWarning(code="NO_PERIOD", message="could not find 'Período' on page 0")
        )
        return ParseResult(warnings=warnings)
    q_start = date.fromisoformat(parse_es_date(m.group(1)))
    q_end = date.fromisoformat(parse_es_date(m.group(2)))
    # derive quarter label from bounds (document may cover a partial quarter)
    quarter = (q_start.month - 1) // 3 + 1
    qs, qe = quarter_bounds(q_start.year, quarter)
    q_label = f"{q_start.year}Q{quarter}"
    full_quarter = (qs, qe) == (q_start, q_end)
    period_label = q_label if full_quarter else f"{q_start.isoformat()}_{q_end.isoformat()}"

    # --- summary rows (page 0) ---
    for line in pages_text[0].splitlines():
        parts = _SUMMARY_ROW_RE.split(line)
        # split() interleaves: ['', 'Total', ' <api tokens> ', 'Total', ' <digital tokens>']
        # the service word appears twice per merged row
        if len(parts) >= 5 and parts[1] == parts[3]:
            service_word = parts[1]
            api_toks = _NUM_TOK_RE.findall(parts[2])
            dig_toks = _NUM_TOK_RE.findall(parts[4])
            service = _SERVICE_MAP[service_word]
            notes = "PCOMUNES: common/shared operations" if service_word == "PCOMUNES" else None
            for toks, iface in (
                (api_toks, InterfaceType.DEDICATED_API),
                (dig_toks, InterfaceType.PSU_INTERFACE),
            ):
                if not toks:
                    warnings.append(
                        ParseWarning(
                            code="EMPTY_SERVICE_ROW",
                            message=f"no numeric data for {service_word}/{iface.value} in summary",
                        )
                    )
                    continue
                before = len(out)
                try:
                    _emit_metrics(
                        out,
                        entity=entity,
                        artifact=artifact,
                        date_or_period=(q_start, q_end, PeriodType.QUARTER, period_label),
                        interface=iface,
                        service=service,
                        tokens=toks,
                        locator="page 0: resumen",
                        is_summary=True,
                        warnings=warnings,
                    )
                except Exception as exc:
                    warnings.append(
                        ParseWarning(
                            code="SUMMARY_ROW",
                            message=f"failed summary row {service_word}/{iface.value}: {exc}",
                        )
                    )
                for obs in out[before:]:
                    if notes:
                        out[out.index(obs)] = obs.model_copy(update={"notes": notes})

    # --- daily pages ---
    section = None
    for page_no, text in enumerate(pages_text[1:], start=1):
        for line in text.splitlines():
            hdr = _SERVICE_HDR_RE.search(line)
            if hdr:
                section = hdr.group(1)
                continue
            if " Total " not in line:
                continue
            mrow = _DATE_ROW_RE.search(line)
            if not mrow:
                continue
            day = date.fromisoformat(parse_es_date(mrow.group(1)))
            label = day.isoformat()
            dig_half = mrow.group(2)
            api_half = mrow.group(4)
            if not dig_half.startswith("Total") or not api_half.startswith("Total"):
                continue  # operation-level rows: not normalized in v0.1
            service_word = _SECTION_SERVICE.get(section or "", "Total")
            service = _SERVICE_MAP[service_word]
            notes = "PCOMUNES: common/shared operations" if service_word == "PCOMUNES" else None
            for half, iface in (
                (api_half, InterfaceType.DEDICATED_API),
                (dig_half, InterfaceType.PSU_INTERFACE),
            ):
                toks = _NUM_TOK_RE.findall(half)
                if not toks:
                    continue
                try:
                    _emit_metrics(
                        out,
                        entity=entity,
                        artifact=artifact,
                        date_or_period=(day, day, PeriodType.DAY, label),
                        interface=iface,
                        service=service,
                        tokens=toks,
                        locator=f"page {page_no}: {section or 'unknown section'}",
                        is_summary=False,
                        warnings=warnings,
                    )
                except Exception as exc:
                    warnings.append(
                        ParseWarning(
                            code="DAY_ROW",
                            message=f"page {page_no} {iface.value} {day}: {exc}",
                        )
                    )
                if notes:
                    for obs in out:
                        if (
                            obs.period_label == label
                            and obs.notes is None
                            and service_word == "PCOMUNES"
                        ):
                            out[out.index(obs)] = obs.model_copy(update={"notes": notes})

    if not out:
        warnings.append(ParseWarning(code="NO_OBS", message="parser produced no observations"))
    return ParseResult(observations=out, warnings=warnings)


name = NAME
version = VERSION
