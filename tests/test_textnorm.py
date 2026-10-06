from psd2_kpi_es.parsers.textnorm import (
    parse_es_date,
    parse_es_number,
    parse_es_percent,
)


def test_parse_es_number_decimal_comma():
    assert parse_es_number("95,81") == 95.81
    assert parse_es_number("0,02") == 0.02


def test_parse_es_number_thousands():
    assert parse_es_number("68.533") == 68533
    assert parse_es_number("1.575") == 1575
    assert parse_es_number("68.533,14") == 68533.14


def test_parse_es_number_plain():
    assert parse_es_number("819") == 819
    assert parse_es_number("100.00") == 100.0
    assert parse_es_number("-4,17") == -4.17


def test_parse_es_percent():
    assert parse_es_percent("95,81%") == 95.81
    assert parse_es_percent("95.81 %") == 95.81
    assert parse_es_percent("0 %") == 0.0


def test_parse_es_date():
    assert parse_es_date("01/04/2024") == "2024-04-01"
    assert parse_es_date("01-04-24") == "2024-04-01"
    assert parse_es_date("9/9/2019") == "2019-09-09"
