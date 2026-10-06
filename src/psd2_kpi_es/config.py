"""Paths and constants. Everything resolves from the repository root."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
DIST_DIR = REPO_ROOT / "dist"
REPORTS_DIR = REPO_ROOT / "reports"

OBSERVATIONS_PARQUET = NORMALIZED_DIR / "observations.parquet"
SOURCES_PARQUET = NORMALIZED_DIR / "sources.parquet"
DUCKDB_PATH = DIST_DIR / "psd2-kpi-es.duckdb"

CATALOG_PATH = Path(__file__).parent / "catalog.toml"

APP_VERSION = "0.1.0"
USER_AGENT = f"psd2-kpi-es/{APP_VERSION} (+https://github.com/Huntsman1756/psd2-kpi-es)"
REQUEST_TIMEOUT_S = 30.0
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024  # 50 MiB safety cap
