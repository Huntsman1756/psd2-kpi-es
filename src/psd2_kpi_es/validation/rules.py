"""Dataset validation rules. Returns a list of violations; empty means clean.

Every violation is a dict: {rule, severity, entity_id?, detail}.
"""

from __future__ import annotations

from datetime import date, timedelta

from psd2_kpi_es.models import Observation


def _viol(rule: str, detail: str, severity: str = "error") -> dict:
    return {"rule": rule, "severity": severity, "detail": detail}


def validate_observations(obs: list[Observation]) -> list[dict]:
    v: list[dict] = []
    seen_keys: dict[tuple, Observation] = {}
    today = date.today() + timedelta(days=45)  # allow near-future quarter ends

    for o in obs:
        tag = f"{o.entity_id}/{o.period_label}/{o.service.value}/{o.metric.value}"

        if o.value is not None:
            # Out-of-range values CAN be genuinely published anomalies (observed
            # in the wild: TDA = -4,17 %). They are kept verbatim for audit
            # fidelity and reported as warnings, not silently nulled.
            if o.metric.value == "availability" and not (0 <= o.value <= 100):
                v.append(
                    _viol(
                        "range",
                        f"{tag}: availability {o.value} out of [0,100]",
                        severity="warning",
                    )
                )
            if o.metric.value in ("error_rate", "request_success_rate") and not (
                0 <= o.value <= 100
            ):
                v.append(
                    _viol("range", f"{tag}: rate {o.value} out of [0,100]", severity="warning")
                )
            if o.metric.value == "response_time" and o.value < 0:
                v.append(_viol("range", f"{tag}: negative response_time"))
            if o.metric.value == "request_count" and o.value < 0:
                v.append(_viol("range", f"{tag}: negative request_count"))

        if o.period_start > o.period_end:
            v.append(_viol("period", f"{tag}: period_start > period_end"))
        if o.period_end > today:
            v.append(_viol("period", f"{tag}: period ends in the future ({o.period_end})"))

        if not o.source_sha256:
            v.append(_viol("provenance", f"{tag}: missing source_sha256"))
        if not o.source_url:
            v.append(_viol("provenance", f"{tag}: missing source_url"))
        if not o.parser_version:
            v.append(_viol("provenance", f"{tag}: missing parser_version"))
        if o.value_status.value == "reported" and o.raw_value is None:
            v.append(_viol("provenance", f"{tag}: reported value without raw_value"))

        key = (
            o.source_sha256,
            o.entity_id,
            o.period_label,
            o.interface_type,
            o.service,
            o.metric,
            o.raw_label,
        )
        if key in seen_keys:
            prev = seen_keys[key]
            if prev.value != o.value:
                v.append(
                    _viol(
                        "duplicate_conflict",
                        f"{tag}: conflicting duplicate values "
                        f"{prev.value} vs {o.value} (sha {o.source_sha256[:8]})",
                    )
                )
        else:
            seen_keys[key] = o

    return v


def validate_referential_integrity(obs: list[Observation], source_ids: set[str]) -> list[dict]:
    bad = {o.source_id for o in obs if o.source_id not in source_ids}
    return (
        [_viol("referential", f"{len(bad)} observations reference unknown source_ids")]
        if bad
        else []
    )
