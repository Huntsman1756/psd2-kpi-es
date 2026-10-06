from datetime import UTC, date, datetime

from psd2_kpi_es.models import (
    Aggregation,
    Comparability,
    InterfaceType,
    Metric,
    Observation,
    PeriodType,
    Service,
    SourceArtifact,
    Unit,
)
from psd2_kpi_es.pipeline import _dedupe


def _obs(source_id="src_a", value=99.0, raw_label="L", retrieved=None):
    return Observation(
        entity_id="e",
        entity_name="E",
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 1),
        period_type=PeriodType.DAY,
        period_label="2025-07-01",
        interface_type=InterfaceType.DEDICATED_API,
        service=Service.ALL,
        metric=Metric.AVAILABILITY,
        value=value,
        unit=Unit.PERCENT,
        aggregation=Aggregation.POINT,
        comparability=Comparability.PARTIAL,
        comparability_group="g",
        source_id=source_id,
        source_url="u",
        source_sha256="s" * 64,
        parser_name="p",
        parser_version="p:1",
        raw_label=raw_label,
        raw_value="x",
        retrieved_at=retrieved or datetime(2026, 1, 1, tzinfo=UTC),
    )


def _src(source_id, filename):
    return SourceArtifact(
        source_id=source_id,
        entity_id="e",
        source_url="u",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        sha256="s" * 64,
        bytes=1,
        filename=filename,
        parser_name="p",
        parser_version="p:1",
    )


def test_xlsx_preferred_over_pdf_same_key():
    arts = [_src("src_pdf", "doc.pdf"), _src("src_xlsx", "doc.xlsx")]
    obs = [_obs("src_pdf", 99.0), _obs("src_xlsx", 99.0)]
    kept, violations = _dedupe(obs, arts)
    assert len(kept) == 1
    assert kept[0].source_id == "src_xlsx"
    assert not violations  # equal values: no conflict


def test_conflicting_duplicate_reported():
    arts = [_src("src_pdf", "doc.pdf"), _src("src_xlsx", "doc.xlsx")]
    obs = [_obs("src_pdf", 99.0), _obs("src_xlsx", 99.01)]
    kept, violations = _dedupe(obs, arts)
    assert len(kept) == 1
    assert violations and violations[0]["rule"] == "duplicate_precision"


def test_different_raw_labels_not_deduped():
    arts = [_src("src_a", "a.pdf")]
    obs = [
        _obs("src_a", 1.0, raw_label="Peticiones OK"),
        _obs("src_a", 2.0, raw_label="Peticiones KO"),
    ]
    kept, _ = _dedupe(obs, arts)
    assert len(kept) == 2
