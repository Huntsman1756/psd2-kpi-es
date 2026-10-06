"""Deterministic Parquet output for observations and sources.

Rows are sorted by a stable logical key so identical inputs produce identical
files (modulo parquet writer metadata).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from psd2_kpi_es.models import Observation, SourceArtifact

OBS_SCHEMA = pa.schema(
    [
        ("observation_id", pa.string()),
        ("entity_id", pa.string()),
        ("entity_name", pa.string()),
        ("period_start", pa.date32()),
        ("period_end", pa.date32()),
        ("period_type", pa.string()),
        ("period_label", pa.string()),
        ("interface_type", pa.string()),
        ("service", pa.string()),
        ("metric", pa.string()),
        ("value", pa.float64()),
        ("unit", pa.string()),
        ("aggregation", pa.string()),
        ("value_status", pa.string()),
        ("metric_definition", pa.string()),
        ("metric_definition_url", pa.string()),
        ("comparability", pa.string()),
        ("comparability_group", pa.string()),
        ("source_id", pa.string()),
        ("source_url", pa.string()),
        ("source_document", pa.string()),
        ("published_at", pa.date32()),
        ("retrieved_at", pa.timestamp("us", tz="UTC")),
        ("source_sha256", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
        ("raw_label", pa.string()),
        ("raw_value", pa.string()),
        ("raw_unit", pa.string()),
        ("interpretation", pa.string()),
        ("notes", pa.string()),
    ]
)

SRC_SCHEMA = pa.schema(
    [
        ("source_id", pa.string()),
        ("entity_id", pa.string()),
        ("source_url", pa.string()),
        ("retrieved_at", pa.timestamp("us", tz="UTC")),
        ("http_status", pa.int32()),
        ("content_type", pa.string()),
        ("filename", pa.string()),
        ("sha256", pa.string()),
        ("bytes", pa.int64()),
        ("published_at", pa.date32()),
        ("period_hint", pa.string()),
        ("parser_name", pa.string()),
        ("parser_version", pa.string()),
    ]
)


def _sort_key(o: Observation) -> tuple:
    return (
        o.entity_id,
        o.period_start,
        o.interface_type.value,
        o.service.value,
        o.metric.value,
        o.raw_label or "",
        o.source_sha256,
    )


def observations_table(obs: list[Observation]) -> pa.Table:
    obs = sorted(obs, key=_sort_key)
    rows = [
        {
            "observation_id": o.observation_id,
            "entity_id": o.entity_id,
            "entity_name": o.entity_name,
            "period_start": o.period_start,
            "period_end": o.period_end,
            "period_type": o.period_type.value,
            "period_label": o.period_label,
            "interface_type": o.interface_type.value,
            "service": o.service.value,
            "metric": o.metric.value,
            "value": o.value,
            "unit": o.unit.value,
            "aggregation": o.aggregation.value,
            "value_status": o.value_status.value,
            "metric_definition": o.metric_definition,
            "metric_definition_url": o.metric_definition_url,
            "comparability": o.comparability.value,
            "comparability_group": o.comparability_group,
            "source_id": o.source_id,
            "source_url": o.source_url,
            "source_document": o.source_document,
            "published_at": o.published_at,
            "retrieved_at": o.retrieved_at,
            "source_sha256": o.source_sha256,
            "parser_name": o.parser_name,
            "parser_version": o.parser_version,
            "raw_label": o.raw_label,
            "raw_value": o.raw_value,
            "raw_unit": o.raw_unit,
            "interpretation": o.interpretation,
            "notes": o.notes,
        }
        for o in obs
    ]
    return pa.Table.from_pylist(rows, schema=OBS_SCHEMA)


def sources_table(srcs: list[SourceArtifact]) -> pa.Table:
    srcs = sorted(srcs, key=lambda s: (s.entity_id, s.retrieved_at, s.sha256))
    rows = [
        {
            "source_id": s.source_id,
            "entity_id": s.entity_id,
            "source_url": s.source_url,
            "retrieved_at": s.retrieved_at,
            "http_status": s.http_status,
            "content_type": s.content_type,
            "filename": s.filename,
            "sha256": s.sha256,
            "bytes": s.bytes,
            "published_at": s.published_at,
            "period_hint": s.period_hint,
            "parser_name": s.parser_name,
            "parser_version": s.parser_version,
        }
        for s in srcs
    ]
    return pa.Table.from_pylist(rows, schema=SRC_SCHEMA)


def write_parquet(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd", write_statistics=True)
