"""Comparability guard: rankings must not mix incompatible groups."""

from psd2_kpi_es.cli import _comparability_groups


def _row(group):
    return {"comparability_group": group, "value": 1.0}


def test_single_group_passes():
    rows = [_row("availability_daily_pct"), _row("availability_daily_pct")]
    assert _comparability_groups(rows) == {"availability_daily_pct"}


def test_mixed_groups_detected():
    rows = [_row("availability_daily_pct"), _row("downtime_daily_pct")]
    assert len(_comparability_groups(rows)) == 2


def test_multi_group_cell_split():
    rows = [{"comparability_group": "g1,g2", "value": 1.0}]
    assert _comparability_groups(rows) == {"g1", "g2"}
