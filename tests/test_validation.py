from datetime import date

from psd2_kpi_es.models import (
    Aggregation,
    Comparability,
    InterfaceType,
    Metric,
    Observation,
    PeriodType,
    Service,
    Unit,
)
from psd2_kpi_es.validation.rules import (
    validate_observations,
    validate_referential_integrity,
)


def _obs(**kw) -> Observation:
    base = dict(
        entity_id="t",
        entity_name="T",
        period_start=date(2025, 7, 1),
        period_end=date(2025, 7, 1),
        period_type=PeriodType.DAY,
        period_label="2025-07-01",
        interface_type=InterfaceType.DEDICATED_API,
        service=Service.ALL,
        metric=Metric.AVAILABILITY,
        value=99.9,
        unit=Unit.PERCENT,
        aggregation=Aggregation.POINT,
        comparability=Comparability.PARTIAL,
        comparability_group="availability_daily_pct",
        source_id="src_x",
        source_url="https://example.test/doc.pdf",
        source_sha256="a" * 64,
        parser_name="t",
        parser_version="t:1",
        raw_label="L",
        raw_value="99,9%",
    )
    base.update(kw)
    return Observation(**base)


def test_clean_observation_passes():
    assert validate_observations([_obs()]) == []


def test_out_of_range_is_warning():
    v = validate_observations([_obs(value=-4.17)])
    assert len(v) == 1 and v[0]["severity"] == "warning"


def test_missing_sha_is_error():
    v = validate_observations([_obs(source_sha256="")])
    assert any(x["rule"] == "provenance" for x in v)


def test_reported_without_raw_value_flagged():
    v = validate_observations([_obs(raw_value=None)])
    assert any(x["rule"] == "provenance" for x in v)


def test_conflicting_duplicates_detected():
    v = validate_observations([_obs(), _obs(value=95.0)])
    assert any(x["rule"] == "duplicate_conflict" for x in v)


def test_referential_integrity():
    obs = [_obs(source_id="src_missing")]
    assert validate_referential_integrity(obs, {"src_x"})
    assert not validate_referential_integrity(obs, {"src_missing"})
