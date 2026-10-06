"""Banco Santander PSD2 statistics parser.

Source: https://www.bancosantander.es/espacio-psd2 links a quarterly summary
PDF ('ES_estadistica_de_rendimiento_y_disponibilidad_-_santand_*.pdf') which
itself links the daily data workbook
'ES-estadisticas_diarias_canales_PSD2.xlsx' via a PDF link annotation.

Workbook layout (verified 2026Q2 asset):
  Resumen              monthly availability per interface
  APIs_DISP            daily dedicated-interface availability (0..1)
  APIs_TMR             daily response time per API operation, labelled
                       'Rendimiento (s)' but values are milliseconds
                       (consistent with the PDF's ms summary and implausible
                       as seconds; transformation documented in notes).
  IntParticulares_*    PSU web interface, retail segment
  MovParticulares_*    PSU mobile interface, retail segment
  IntEmpresas_*        PSU web interface, business segment
  MovEmpresas_*        PSU mobile interface, business segment

Only the 'santand' (Spain) PDF is used; the 'sucursa' (international
branches) PDF is deliberately excluded.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

import openpyxl
from pypdf import PdfReader

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

NAME = "santander"
VERSION = "santander:1"

_INDEX_PDF_RE = re.compile(
    r"https?://[^\"'\s]*estadistica_de_rendimiento_y_disponibilidad_-_santand[^\"'\s]*\.pdf",
    re.IGNORECASE,
)
_SHEET_RE = re.compile(
    r"(APIs|IntParticulares|MovParticulares|IntEmpresas|MovEmpresas)_(DISP|TMR)$"
)
_EN_DATE_RE = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{4})")
_EN_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

_IFACE = {
    "APIs": (InterfaceType.DEDICATED_API, None),
    "IntParticulares": (InterfaceType.WEB, "particulares"),
    "MovParticulares": (InterfaceType.MOBILE, "particulares"),
    "IntEmpresas": (InterfaceType.WEB, "empresas"),
    "MovEmpresas": (InterfaceType.MOBILE, "empresas"),
}

_TMR_NOTE = (
    "Sheet header says 'Rendimiento (s)' but magnitudes are milliseconds; "
    "stored as ms. See docs/sources/santander.md."
)


def discover_links(index_html: bytes) -> list[str]:
    text = index_html.decode("utf-8", errors="replace")
    return sorted(set(_INDEX_PDF_RE.findall(text)))


def discover_nested(content: bytes) -> list[str]:
    """Extract document links embedded in the summary PDF."""
    if content[:5] != b"%PDF-":
        return []
    urls = set()
    try:
        reader = PdfReader(io.BytesIO(content))
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                uri = (annot.get_object().get("/A") or {}).get("/URI")
                if uri and uri.lower().endswith((".xlsx", ".xls", ".csv")):
                    urls.add(uri)
    except Exception:
        return []
    return sorted(urls)


def period_hint(url: str) -> str | None:
    return None  # the xlsx URN is stable; period lives inside the document


def _en_date(text: str) -> date | None:
    m = _EN_DATE_RE.search(str(text))
    if not m:
        return None
    return date(int(m.group(3)), _EN_MONTHS[m.group(1)], int(m.group(2)))


def _day(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return _en_date(v)
    return None


def _obs(
    *,
    entity,
    artifact,
    start,
    end,
    ptype,
    plabel,
    interface,
    service,
    metric,
    value,
    unit,
    group,
    raw_label,
    raw_value,
    raw_unit,
    locator,
    notes=None,
) -> Observation:
    return Observation(
        entity_id=entity.entity_id,
        entity_name=entity.legal_name,
        period_start=start,
        period_end=end,
        period_type=ptype,
        period_label=plabel,
        interface_type=interface,
        service=service,
        metric=metric,
        value=value,
        unit=unit,
        aggregation=Aggregation.DAILY_MEAN if ptype is PeriodType.DAY else Aggregation.MEAN,
        comparability=Comparability.PARTIAL,
        comparability_group=group,
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


def _service_of(tipo: str) -> Service:
    t = (tipo or "").strip().upper()
    return {
        "AIS": Service.AIS,
        "PIS": Service.PIS,
        "CBPII": Service.PIISP,
        "PIISP": Service.PIISP,
        "FCS": Service.PIISP,
    }.get(t, Service.UNKNOWN)


def _parse_xlsx(artifact, content, entity) -> ParseResult:
    warnings: list[ParseWarning] = []
    out: list[Observation] = []
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    for sheet in wb.sheetnames:
        m = _SHEET_RE.fullmatch(sheet)
        ws = wb[sheet]
        if sheet == "Resumen":
            out += _parse_resumen(ws, artifact, entity, warnings)
            continue
        if not m:
            continue
        channel, kind = m.group(1), m.group(2)
        iface, segment = _IFACE[channel]

        if sheet == "APIs_TMR":
            out += _parse_apis_tmr(ws, artifact, entity, iface, warnings)
            continue

        metric = Metric.AVAILABILITY if kind == "DISP" else Metric.RESPONSE_TIME
        unit = Unit.PERCENT if kind == "DISP" else Unit.SECONDS
        group = "availability_daily_pct" if kind == "DISP" else "response_time_daily_mean_seconds"
        scale = 100.0 if kind == "DISP" else 1.0
        raw_label = "Disponibilidad" if kind == "DISP" else "Rendimiento (s)"
        seg_note = f"PSU interface segment: {segment}" if segment else None

        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            day = _day(row[0])
            val = row[1] if len(row) > 1 else None
            if day is None or val is None:
                continue
            try:
                v = float(val) * scale
            except (TypeError, ValueError):
                warnings.append(ParseWarning(code="CELL", message=f"{sheet} {row[0]} {val!r}"))
                continue
            out.append(
                _obs(
                    entity=entity,
                    artifact=artifact,
                    start=day,
                    end=day,
                    ptype=PeriodType.DAY,
                    plabel=day.isoformat(),
                    interface=iface,
                    service=Service.ALL,
                    metric=metric,
                    value=v,
                    unit=unit,
                    group=group,
                    raw_label=raw_label,
                    raw_value=str(val),
                    raw_unit="ratio" if kind == "DISP" else "s",
                    locator=f"sheet '{sheet}'",
                    notes=seg_note,
                )
            )
    return ParseResult(observations=out, warnings=warnings)


def _parse_apis_tmr(ws, artifact, entity, iface, warnings):
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        day = _day(row[0])
        tipo, api_op, val = row[1], row[2], row[3] if len(row) > 3 else None
        if day is None or val is None or str(val).strip() == "-":
            continue  # '-' = no requests that day (legit not-reported)
        try:
            v = float(val)
        except (TypeError, ValueError):
            warnings.append(ParseWarning(code="CELL", message=f"APIs_TMR {row[0]} {val!r}"))
            continue
        out.append(
            _obs(
                entity=entity,
                artifact=artifact,
                start=day,
                end=day,
                ptype=PeriodType.DAY,
                plabel=day.isoformat(),
                interface=iface,
                service=_service_of(str(tipo)),
                metric=Metric.RESPONSE_TIME,
                value=v,
                unit=Unit.MS,
                group="response_time_daily_mean_ms",
                raw_label=f"Rendimiento (s) — {api_op}",
                raw_value=str(val),
                raw_unit="s",
                locator="sheet 'APIs_TMR'",
                notes=_TMR_NOTE,
            )
        )
    return out


def _parse_resumen(ws, artifact, entity, warnings):
    """Resumen sheet: month headers over blocks of interface availability."""
    out = []
    # row 2 holds month names over each block of ~5-6 columns; block start col
    rows = list(ws.iter_rows(values_only=True))
    month_cols = []
    for r in rows:
        for ci, v in enumerate(r):
            if isinstance(v, str) and v.strip() in (
                "Enero",
                "Febrero",
                "Marzo",
                "Abril",
                "Mayo",
                "Junio",
                "Julio",
                "Agosto",
                "Septiembre",
                "Octubre",
                "Noviembre",
                "Diciembre",
            ):
                year = None
                m = re.match(r"(\w+)\s+(\d{4})", v.strip())
                if m:
                    from psd2_kpi_es.parsers.unicaja import _MONTHS

                    month = _MONTHS[m.group(1).lower()]
                    year = int(m.group(2))
                    month_cols.append((ci, year, month))
    # rows with 'Interfaz' label define interface names per block
    for ci, year, month in month_cols:
        col = ci + 3  # value column sits ~3 right of the month header
        if col >= len(rows[0]):
            continue
        for r in rows:
            name = r[ci + 0] if ci < len(r) else None
            val = r[col] if col < len(r) else None
            if not isinstance(name, str) or val is None:
                continue
            lname = name.strip().lower()
            if lname in ("interfaz", "disponibilidad", ""):
                continue
            iface = _resumen_iface(lname)
            if iface is None:
                continue
            try:
                v = float(val) * 100
            except (TypeError, ValueError):
                continue
            import calendar

            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            segment = (
                "empresas"
                if "empres" in lname
                else ("particulares" if "particular" in lname else None)
            )
            service = Service.ALL
            if "ais" in lname:
                service = Service.AIS
            elif "pis" in lname and "piis" not in lname:
                service = Service.PIS
            elif "piis" in lname:
                service = Service.PIISP
            out.append(
                _obs(
                    entity=entity,
                    artifact=artifact,
                    start=start,
                    end=end,
                    ptype=PeriodType.MONTH,
                    plabel=f"{year}-{month:02d}",
                    interface=iface,
                    service=service,
                    metric=Metric.AVAILABILITY,
                    value=v,
                    unit=Unit.PERCENT,
                    group="availability_daily_pct",
                    raw_label=f"Disponibilidad {name.strip()}",
                    raw_value=str(val),
                    raw_unit="ratio",
                    locator="sheet 'Resumen'",
                    notes=f"PSU interface segment: {segment}" if segment else None,
                )
            )
    return out


def _resumen_iface(lname: str) -> InterfaceType | None:
    if "api" in lname:
        return InterfaceType.DEDICATED_API
    if "web" in lname:
        return InterfaceType.WEB
    if "app" in lname:
        return InterfaceType.MOBILE
    return None


def parse(artifact: SourceArtifact, content: bytes, entity: Entity) -> ParseResult:
    fn = (artifact.filename or artifact.source_url).lower()
    ctype = (artifact.content_type or "").lower()
    if fn.endswith(".xlsx") or "spreadsheet" in ctype:
        return _parse_xlsx(artifact, content, entity)
    # the summary PDF is a discovery artifact; the XLSX carries the data
    return ParseResult(
        warnings=[
            ParseWarning(
                code="SKIPPED",
                message="summary PDF used for discovery only; daily data in linked XLSX",
            )
        ]
    )


name = NAME
version = VERSION
