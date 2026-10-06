"""Immutable, content-addressed raw artifact store.

Layout:

    data/raw/<entity_id>/blobs/<sha256>          artifact bytes (extension in meta)
    data/raw/<entity_id>/meta/<sha256>.jsonl     one JSON line per retrieval event
    data/raw/<entity_id>/fetch-log.jsonl         every retrieval attempt, incl. failures

A blob is never overwritten: identical content maps to the same sha256, and a
changed document produces a new sha256 file while the old one is preserved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from psd2_kpi_es.config import RAW_DIR


@dataclass
class RetrievalEvent:
    retrieved_at: str  # ISO-8601 UTC
    url: str
    http_status: int | None
    content_type: str | None
    bytes: int
    sha256: str | None
    ok: bool
    error: str | None = None
    filename: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entity_dir(entity_id: str) -> Path:
    return RAW_DIR / entity_id


def blob_path(entity_id: str, sha256: str) -> Path:
    return _entity_dir(entity_id) / "blobs" / sha256


def meta_path(entity_id: str, sha256: str) -> Path:
    return _entity_dir(entity_id) / "meta" / f"{sha256}.jsonl"


def fetch_log_path(entity_id: str) -> Path:
    return _entity_dir(entity_id) / "fetch-log.jsonl"


def record_fetch(
    entity_id: str,
    url: str,
    content: bytes | None,
    http_status: int | None,
    content_type: str | None,
    filename: str | None = None,
    error: str | None = None,
) -> RetrievalEvent:
    """Persist artifact bytes (if any) and append retrieval metadata.

    Returns the event describing what happened. Never mutates an existing blob.
    """
    entity_dir = _entity_dir(entity_id)
    (entity_dir / "blobs").mkdir(parents=True, exist_ok=True)
    (entity_dir / "meta").mkdir(parents=True, exist_ok=True)

    sha = sha256_bytes(content) if content is not None else None
    event = RetrievalEvent(
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        url=url,
        http_status=http_status,
        content_type=content_type,
        bytes=len(content) if content is not None else 0,
        sha256=sha,
        ok=content is not None,
        error=error,
        filename=filename,
    )
    line = json.dumps(vars(event), sort_keys=True)

    if content is not None and sha is not None:
        bp = blob_path(entity_id, sha)
        if not bp.exists():
            # atomic-ish write: temp then rename
            tmp = bp.with_suffix(".tmp")
            tmp.write_bytes(content)
            tmp.replace(bp)
        with open(meta_path(entity_id, sha), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    with open(fetch_log_path(entity_id), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

    return event


def list_artifacts(entity_id: str) -> list[dict]:
    """One dict per unique artifact (sha256): first-seen metadata + stats."""
    meta_dir = _entity_dir(entity_id) / "meta"
    if not meta_dir.exists():
        return []
    artifacts = []
    for mf in sorted(meta_dir.glob("*.jsonl")):
        events = [
            json.loads(line) for line in mf.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        if not events:
            continue
        first, last = events[0], events[-1]
        artifacts.append(
            {
                "sha256": mf.stem,
                "first_retrieved_at": first["retrieved_at"],
                "last_retrieved_at": last["retrieved_at"],
                "retrieval_count": len(events),
                "source_url": last["url"],
                "http_status": last["http_status"],
                "content_type": last["content_type"],
                "bytes": last["bytes"],
                "filename": last.get("filename"),
                "blob_path": str(blob_path(entity_id, mf.stem)),
            }
        )
    return artifacts


def read_blob(entity_id: str, sha256: str) -> bytes:
    return blob_path(entity_id, sha256).read_bytes()
