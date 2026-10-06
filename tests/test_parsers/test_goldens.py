"""Golden tests: real fixture artifact -> full expected observation set.

Regenerate goldens with: GOLDEN_UPDATE=1 uv run pytest tests/test_parsers
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from psd2_kpi_es.parsers import caixabank, renta4, santander, unicaja
from tests.conftest import ENTITIES, FIXTURES, GOLDENS, make_artifact, obs_digest

CASES = [
    (
        "renta4",
        renta4,
        "PublicacionEstadisticasRenta4_PSD2_2T24.pdf",
        "https://www.r4.com/resources/pdf/PublicacionEstadisticasRenta4_PSD2_2T24.pdf",
        "2024Q2",
    ),
    (
        "unicaja",
        unicaja,
        "psd2-estadisticas-unicaja-del-3T2025.pdf",
        "https://www.unicajabanco.es/content/dam/unicaja/documentos/psd2-estadisticas-unicaja-del-3T2025.pdf",
        "2025Q3",
    ),
    (
        "caixabank",
        caixabank,
        "CaixaBank-2026Q2-InformeTrimestralPSD2.xlsx",
        "https://www.caixabank.es/deployedfiles/empresas/Estaticos/pdf/BancaDistancia/CaixaBank-2026Q2-InformeTrimestralPSD2.xlsx",
        "2026Q2",
    ),
    (
        "caixabank",
        caixabank,
        "caixabank-2025q4-psd2.pdf",
        "https://www.imagin.com/documents/554420/699403/caixabank-2025q4-psd2.pdf",
        "2025Q4",
    ),
    (
        "santander",
        santander,
        "ES-estadisticas_diarias_canales_PSD2.xlsx",
        "https://assets.santandermedia.com/adobe/assets/urn:aaid:aem:94ea5fec/original/as/ES-estadisticas_diarias_canales_PSD2.xlsx",
        None,
    ),
]


@pytest.mark.parametrize(
    "entity_id,parser,filename,url,hint",
    CASES,
    ids=[c[2] for c in CASES],
)
def test_parser_golden(entity_id, parser, filename, url, hint):
    fixture = FIXTURES / entity_id / filename
    art = make_artifact(fixture, entity_id, parser.NAME, parser.VERSION, url=url, period_hint=hint)
    result = parser.parse(art, fixture.read_bytes(), ENTITIES[entity_id])
    assert result.observations, f"no observations from {filename}"
    got = obs_digest(result.observations)

    golden = GOLDENS / entity_id / f"{Path(filename).stem}.json"
    if os.environ.get("GOLDEN_UPDATE"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(json.dumps(got, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip("golden updated")
    assert golden.exists(), f"missing golden {golden}; run with GOLDEN_UPDATE=1"
    expected = json.loads(golden.read_text(encoding="utf-8"))
    assert got == expected, (
        f"{len(got)} vs {len(expected)} rows; diff indicates parser behavior change"
    )


def test_no_parse_warnings_on_renta4_golden():
    """The reference document must parse with only the known benign warnings."""
    fixture = FIXTURES / "renta4" / "PublicacionEstadisticasRenta4_PSD2_2T24.pdf"
    art = make_artifact(fixture, "renta4", renta4.NAME, renta4.VERSION)
    result = renta4.parse(art, fixture.read_bytes(), ENTITIES["renta4"])
    bad = [w for w in result.warnings if w.code not in ("EMPTY_SERVICE_ROW",)]
    assert not bad, [w.model_dump() for w in bad]
