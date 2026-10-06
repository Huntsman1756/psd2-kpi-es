"""Load the entity/source catalog."""

from __future__ import annotations

import tomllib

from psd2_kpi_es.config import CATALOG_PATH
from psd2_kpi_es.models import Entity, SourceDocument


def load_catalog(path=None) -> dict[str, tuple[Entity, list[SourceDocument]]]:
    path = path or CATALOG_PATH
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    catalog: dict[str, tuple[Entity, list[SourceDocument]]] = {}
    for entity_id, spec in raw.get("entities", {}).items():
        entity = Entity(
            entity_id=entity_id,
            legal_name=spec["legal_name"],
            brand_name=spec["brand_name"],
            country=spec.get("country", "ES"),
            website=spec.get("website"),
            lei=spec.get("lei"),
        )
        sources = [
            SourceDocument(
                kind=s["kind"],
                url=s["url"],
                parser=s["parser"],
                notes=s.get("notes"),
            )
            for s in spec.get("sources", [])
        ]
        catalog[entity_id] = (entity, sources)
    return catalog
