"""Pipeline orchestration: fetch -> parse -> validate -> publish.

fetch and parse are deliberately separate operations: parsing works fully
offline on the raw artifact store.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from psd2_kpi_es import config
from psd2_kpi_es.acquisition import fetch as acq
from psd2_kpi_es.acquisition import rawstore
from psd2_kpi_es.catalog import load_catalog
from psd2_kpi_es.models import ParseResult, ParseWarning, SourceArtifact
from psd2_kpi_es.parsers import get_parser
from psd2_kpi_es.storage import duckdb as storage_duckdb
from psd2_kpi_es.storage import parquet as storage_parquet
from psd2_kpi_es.validation import rules

log = logging.getLogger(__name__)


def fetch_entity(entity_id: str) -> list[str]:
    """Fetch index pages, discover document links, download each document.

    Returns the list of document URLs discovered.
    """
    _entity, sources = load_catalog()[entity_id]
    parser = get_parser(sources[0].parser)
    discovered: list[str] = []
    with acq.make_client() as client:
        for src in sources:
            if src.kind != "index":
                acq.fetch_and_store(client, entity_id, src.url)
                continue
            event = acq.fetch_and_store(client, entity_id, src.url)
            if not event.sha256:
                continue
            index_html = rawstore.read_blob(entity_id, event.sha256)
            for url in parser.discover_links(index_html):
                discovered.append(url)
                try:
                    doc_event = acq.fetch_and_store(client, entity_id, url)
                except Exception as exc:
                    log.warning("fetch failed %s: %s", url, exc)
                    continue
                # second-level discovery (e.g. XLSX linked inside a PDF)
                if doc_event.sha256 and hasattr(parser, "discover_nested"):
                    try:
                        content = rawstore.read_blob(entity_id, doc_event.sha256)
                        for nested_url in parser.discover_nested(content) or []:
                            discovered.append(nested_url)
                            try:
                                acq.fetch_and_store(client, entity_id, nested_url)
                            except Exception as exc:
                                log.warning("fetch failed %s: %s", nested_url, exc)
                    except Exception as exc:
                        log.warning("nested discovery failed %s: %s", url, exc)
    return discovered


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _to_source_artifact(
    entity_id: str, meta: dict, parser_name: str, parser_version: str, period_hint: str | None
) -> SourceArtifact:
    return SourceArtifact(
        source_id=SourceArtifact.make_id(meta["sha256"]),
        entity_id=entity_id,
        source_url=meta["source_url"],
        retrieved_at=_parse_dt(meta["first_retrieved_at"]),
        http_status=meta["http_status"],
        content_type=meta["content_type"],
        filename=meta["filename"],
        sha256=meta["sha256"],
        bytes=meta["bytes"],
        published_at=None,
        period_hint=period_hint,
        parser_name=parser_name,
        parser_version=parser_version,
    )


def parse_entity(entity_id: str) -> tuple[list, list[SourceArtifact], list[ParseWarning]]:
    """Parse all stored document artifacts for an entity. Fully offline."""
    entity, sources = load_catalog()[entity_id]
    parser = get_parser(sources[0].parser)

    artifacts: list[SourceArtifact] = []
    observations = []
    warnings: list[ParseWarning] = []

    for meta in rawstore.list_artifacts(entity_id):
        ctype = (meta["content_type"] or "").lower()
        hint = parser.period_hint(meta["source_url"])
        art = _to_source_artifact(entity_id, meta, parser.name, parser.version, hint)
        artifacts.append(art)
        if "html" in ctype:
            continue  # index pages are provenance, not data documents
        content = rawstore.read_blob(entity_id, meta["sha256"])
        try:
            result: ParseResult = parser.parse(art, content, entity)
            observations.extend(result.observations)
            warnings.extend(result.warnings)
        except Exception as exc:
            warnings.append(
                ParseWarning(
                    code="PARSE_ERROR",
                    message=f"{meta['filename']}: {exc.__class__.__name__}: {exc}",
                )
            )
    return observations, artifacts, warnings


def _dedupe(observations, artifacts) -> tuple[list, list[dict]]:
    """One observation per logical key.

    Publishers sometimes ship the same period in two artifacts (CaixaBank
    publishes 2026Q2 both as XLSX and PDF). Key = (entity, period, interface,
    service, metric, raw_label). Preference: .xlsx > .pdf > other, then latest
    retrieved_at. Conflicting values are reported, not silently merged.
    """
    fmt_rank = {}
    for a in artifacts:
        fn = (a.filename or "").lower()
        fmt_rank[a.source_id] = 0 if fn.endswith(".xlsx") else (1 if fn.endswith(".pdf") else 2)

    groups: dict[tuple, list] = {}
    for o in observations:
        key = (
            o.entity_id,
            o.period_label,
            o.period_type.value,
            o.interface_type.value,
            o.service.value,
            o.metric.value,
            o.raw_label,
        )
        groups.setdefault(key, []).append(o)

    kept, violations = [], []
    for key, obs in groups.items():
        if len(obs) == 1:
            kept.append(obs[0])
            continue
        obs.sort(key=lambda o: (fmt_rank.get(o.source_id, 9), str(o.retrieved_at)))
        winner = obs[0]
        for loser in obs[1:]:
            if loser.value != winner.value:
                violations.append(
                    {
                        "rule": "duplicate_precision",
                        "severity": "warning",
                        "detail": (
                            f"{key}: duplicate observations with different values "
                            f"{winner.value} (kept, src {winner.source_id[:12]}) vs "
                            f"{loser.value} (dropped, src {loser.source_id[:12]})"
                        ),
                    }
                )
        kept.append(winner)
    return kept, violations


def publish(observations, artifacts) -> list:
    """Validate and write parquet + duckdb. Returns validation violations."""
    observations, dup_violations = _dedupe(observations, artifacts)
    source_ids = {s.source_id for s in artifacts}
    violations = dup_violations
    violations += rules.validate_observations(observations)
    violations += rules.validate_referential_integrity(observations, source_ids)
    storage_parquet.write_parquet(
        storage_parquet.observations_table(observations), config.OBSERVATIONS_PARQUET
    )
    storage_parquet.write_parquet(storage_parquet.sources_table(artifacts), config.SOURCES_PARQUET)
    storage_duckdb.build_duckdb()
    return violations


def ingest_entity(entity_id: str) -> dict:
    fetch_entity(entity_id)
    obs, arts, warns = parse_entity(entity_id)
    violations = publish(obs, arts)
    return {
        "entity": entity_id,
        "observations": len(obs),
        "artifacts": len(arts),
        "warnings": [w.model_dump() for w in warns],
        "violations": violations,
    }
