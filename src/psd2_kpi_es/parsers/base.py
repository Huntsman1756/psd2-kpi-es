"""Parser contract.

A parser receives a *local* artifact (bytes already in the raw store) and
produces canonical observations. It never performs network I/O.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Protocol

from psd2_kpi_es.models import Entity, ParseResult, SourceArtifact


class Parser(Protocol):
    name: str
    version: str

    def discover_links(self, index_html: bytes) -> list[str]:
        """Extract document URLs from a fetched index page."""
        ...

    def period_hint(self, url: str) -> str | None:
        """Best-effort period label (e.g. '2025Q3') derivable from a document URL."""
        ...

    def discover_nested(self, content: bytes) -> list[str]:
        """URLs embedded *inside* a fetched artifact (e.g. XLSX linked from a
        summary PDF). Optional; default: none."""
        return []

    def parse(
        self,
        artifact: SourceArtifact,
        content: bytes,
        entity: Entity,
    ) -> ParseResult: ...


def quarter_label(year: int, quarter: int) -> str:
    return f"{year}Q{quarter}"


def quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    first_month = (quarter - 1) * 3 + 1
    start = date(year, first_month, 1)
    if first_month == 10:
        end = date(year, 12, 31)
    else:
        end = date(year, first_month + 3, 1) - timedelta(days=1)
    return start, end


def parse_period_label(label: str) -> tuple[date, date, str]:
    """'2025Q3' -> (2025-07-01, 2025-09-30, 'quarter'). '2025-03' -> month. '2025-03-14' -> day."""
    m = re.fullmatch(r"(\d{4})Q([1-4])", label)
    if m:
        start, end = quarter_bounds(int(m.group(1)), int(m.group(2)))
        return start, end, "quarter"
    m = re.fullmatch(r"(\d{4})-(\d{2})", label)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        start = date(y, mo, 1)
        end = date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1)
        return start, end, "month"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", label)
    if m:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return d, d, "day"
    # explicit range labels (e.g. '2019-09-14_2019-12-16', Renta 4's first
    # publication spans the PSD2 go-live window rather than a calendar quarter)
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", label)
    if m:
        return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)), "range"
    raise ValueError(f"unrecognized period label: {label!r}")
