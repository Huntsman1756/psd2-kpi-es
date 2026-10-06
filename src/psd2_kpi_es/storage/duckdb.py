"""Build the derived DuckDB database from the published Parquet files."""

from __future__ import annotations

import duckdb

from psd2_kpi_es import config
from psd2_kpi_es.models import DATASET_SCHEMA_VERSION


def build_duckdb(path=None) -> None:
    path = path or config.DUCKDB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE OR REPLACE VIEW observations AS "
            f"SELECT * FROM read_parquet('{config.OBSERVATIONS_PARQUET.as_posix()}')"
        )
        con.execute(
            "CREATE OR REPLACE VIEW sources AS "
            f"SELECT * FROM read_parquet('{config.SOURCES_PARQUET.as_posix()}')"
        )
        con.execute(
            "CREATE OR REPLACE TABLE build_info AS SELECT "
            f"{DATASET_SCHEMA_VERSION} AS dataset_schema_version"
        )
    finally:
        con.close()
