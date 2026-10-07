"""CLI contract used by scripts/ingest_all.sh: typed domain failures must
exit 5 and emit {"error_code": ...} JSON on stderr; unexpected errors keep
the default non-zero exit. Locked in place by these tests because the
scheduled workflows depend on it.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from psd2_kpi_es import cli, pipeline
from psd2_kpi_es.errors import NetworkError, SourceNotFoundError

runner = CliRunner()


def test_ingest_source_not_found_exits_5_with_code(monkeypatch):
    def boom(entity_id: str) -> dict:
        raise SourceNotFoundError("404 for https://example.test/index")

    monkeypatch.setattr(pipeline, "ingest_entity", boom)
    res = runner.invoke(cli.app, ["ingest", "renta4"])
    assert res.exit_code == 5
    line = next(x for x in res.stderr.splitlines() if x.startswith('{"entity"'))
    err = json.loads(line)
    assert err["error_code"] == "SOURCE_NOT_FOUND"


def test_ingest_other_domain_errors_also_exit_5(monkeypatch):
    def boom(entity_id: str) -> dict:
        raise NetworkError("timeout")

    monkeypatch.setattr(pipeline, "ingest_entity", boom)
    res = runner.invoke(cli.app, ["ingest", "renta4"])
    assert res.exit_code == 5
    line = next(x for x in res.stderr.splitlines() if x.startswith('{"entity"'))
    assert json.loads(line)["error_code"] == "NETWORK_ERROR"


def test_ingest_success_exit_0(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "ingest_entity",
        lambda entity_id: {
            "entity": entity_id,
            "observations": 3,
            "artifacts": 1,
            "warnings": [],
            "violations": [],
        },
    )
    res = runner.invoke(cli.app, ["ingest", "renta4"])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["observations"] == 3
