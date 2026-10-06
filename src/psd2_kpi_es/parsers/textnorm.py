"""Shared text/number normalization helpers for parsers.

Everything here is deterministic and locale-aware for Spanish publications
('95,81%' -> 95.81, '1.575' -> 1575 when thousands context applies).
"""

from __future__ import annotations

import re

_NUM_RE = re.compile(r"-?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|-?\d+(?:[.,]\d+)?")


def parse_es_number(text: str) -> float:
    """Parse a Spanish-formatted number: '95,81' -> 95.81, '68.533' -> 68533.

    Rules: ',' is the decimal separator; '.' or thin/regular space are
    thousands separators. A lone '.' with 1-2 decimals is treated as decimal
    point (e.g. '100.00' in English-style docs).
    """
    t = text.strip().replace("\xa0", " ").replace(" ", "")
    if not t:
        raise ValueError("empty numeric string")
    if "," in t:
        # '68.533,14' or '95,81' or '1.575'
        t = t.replace(".", "").replace(",", ".")
        return float(t)
    # no comma: dots may be thousands ('68.533') or decimals ('100.00')
    if t.count(".") == 1:
        int_part, frac = t.split(".")
        if len(frac) == 3 and len(int_part.lstrip("-")) <= 3:
            return float(t.replace(".", ""))
        return float(t)
    if t.count(".") > 1:
        return float(t.replace(".", ""))
    return float(t)


def parse_es_percent(text: str) -> float:
    """'95,81%' / '95.81 %' -> 95.81"""
    t = text.strip().rstrip("%").strip()
    return parse_es_number(t)


def parse_es_date(text: str) -> str:
    """'01/04/2024' or '01-04-24' -> '2024-04-01' (ISO)."""
    t = text.strip()
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", t)
    if not m:
        raise ValueError(f"not a DD/MM/YYYY date: {text!r}")
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    return f"{y:04d}-{mo:02d}-{d:02d}"


def first_number(text: str) -> str | None:
    m = _NUM_RE.search(text)
    return m.group(0) if m else None
