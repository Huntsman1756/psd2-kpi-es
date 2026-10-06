from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from psd2_kpi_es.models import Entity, SourceArtifact

FIXTURES = Path(__file__).parent / "fixtures"
GOLDENS = Path(__file__).parent / "goldens"

ENTITIES = {
    "renta4": Entity(
        entity_id="renta4",
        legal_name="Renta 4 Banco, S.A.",
        brand_name="Renta 4",
    ),
    "unicaja": Entity(
        entity_id="unicaja",
        legal_name="Unicaja Banco, S.A.",
        brand_name="Unicaja",
    ),
    "caixabank": Entity(
        entity_id="caixabank",
        legal_name="CaixaBank, S.A.",
        brand_name="CaixaBank",
    ),
    "santander": Entity(
        entity_id="santander",
        legal_name="Banco Santander, S.A.",
        brand_name="Santander",
    ),
}


def make_artifact(
    path: Path,
    entity_id: str,
    parser_name: str,
    parser_version: str,
    url: str | None = None,
    period_hint: str | None = None,
) -> SourceArtifact:
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    return SourceArtifact(
        source_id=SourceArtifact.make_id(sha),
        entity_id=entity_id,
        source_url=url or f"fixture://{path.name}",
        retrieved_at=datetime(2026, 10, 6, tzinfo=UTC),
        http_status=200,
        content_type=None,
        filename=path.name,
        sha256=sha,
        bytes=len(content),
        period_hint=period_hint,
        parser_name=parser_name,
        parser_version=parser_version,
    )


def obs_digest(observations) -> list[dict]:
    """Deterministic projection of observations used for golden comparison."""
    rows = [
        {
            "period_label": o.period_label,
            "interface_type": o.interface_type.value,
            "service": o.service.value,
            "metric": o.metric.value,
            "value": o.value,
            "unit": o.unit.value,
            "aggregation": o.aggregation.value,
            "comparability_group": o.comparability_group,
            "raw_label": o.raw_label,
            "raw_value": o.raw_value,
        }
        for o in observations
    ]
    rows.sort(key=lambda r: tuple(str(v) for v in r.values()))
    return rows


def golden_path(entity_id: str, name: str) -> Path:
    return GOLDENS / entity_id / f"{name}.json"


@pytest.fixture
def entities():
    return ENTITIES
