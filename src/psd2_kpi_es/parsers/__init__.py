"""Parser registry: entity/parser name -> module implementing the Parser protocol."""

from __future__ import annotations

from psd2_kpi_es.parsers import caixabank, renta4, santander, unicaja

_REGISTRY = {
    "renta4": renta4,
    "unicaja": unicaja,
    "caixabank": caixabank,
    "santander": santander,
}


def get_parser(name: str):
    return _REGISTRY[name]


def available_parsers() -> list[str]:
    return sorted(_REGISTRY)
