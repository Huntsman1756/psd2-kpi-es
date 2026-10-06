from datetime import date

import pytest

from psd2_kpi_es.parsers.base import parse_period_label, quarter_bounds


def test_quarter_bounds():
    assert quarter_bounds(2025, 1) == (date(2025, 1, 1), date(2025, 3, 31))
    assert quarter_bounds(2025, 4) == (date(2025, 10, 1), date(2025, 12, 31))
    assert quarter_bounds(2024, 2) == (date(2024, 4, 1), date(2024, 6, 30))


def test_parse_period_label():
    assert parse_period_label("2025Q3") == (date(2025, 7, 1), date(2025, 9, 30), "quarter")
    assert parse_period_label("2025-03") == (date(2025, 3, 1), date(2025, 3, 31), "month")
    assert parse_period_label("2025-12") == (date(2025, 12, 1), date(2025, 12, 31), "month")
    assert parse_period_label("2025-03-14") == (date(2025, 3, 14), date(2025, 3, 14), "day")
    with pytest.raises(ValueError):
        parse_period_label("Q3-2025")
