"""Published anomalies must be preserved verbatim and flagged, never
corrected or dropped (docs/philosophy: the dataset records what the
publisher said, not what it should have said).

Fixture: Renta 4 4T2024, which publishes TDA=-4,17% on 2024-10-06 and
2024-10-12 — a value outside the plausible [0,100] availability range.
"""

from __future__ import annotations

from psd2_kpi_es.models import ValueStatus
from psd2_kpi_es.parsers import renta4
from psd2_kpi_es.validation.rules import validate_observations
from tests.conftest import ENTITIES, FIXTURES, make_artifact

_FIXTURE = FIXTURES / "renta4" / "PublicacionEstadisticasRenta4_PSD2_4T24.pdf"


def _parse():
    art = make_artifact(_FIXTURE, "renta4", renta4.NAME, renta4.VERSION)
    return renta4.parse(art, _FIXTURE.read_bytes(), ENTITIES["renta4"])


def test_negative_availability_kept_verbatim():
    result = _parse()
    neg = [
        o
        for o in result.observations
        if o.metric.value == "availability" and o.value is not None and o.value < 0
    ]
    assert neg, "expected the published -4,17% anomalies to be preserved"
    for o in neg:
        assert o.value == -4.17
        assert o.raw_value == "-4,17%"
        assert o.value_status is ValueStatus.REPORTED
        assert o.interpretation == "verbatim"
        assert {o.period_label for o in neg} == {"2024-10-06", "2024-10-12"}


def test_anomaly_flagged_as_warning_not_removed():
    result = _parse()
    violations = validate_observations(result.observations)
    range_v = [v for v in violations if v["rule"] == "range" and "-4.17" in v["detail"]]
    assert range_v, "anomaly must be flagged"
    assert all(v["severity"] == "warning" for v in range_v)
