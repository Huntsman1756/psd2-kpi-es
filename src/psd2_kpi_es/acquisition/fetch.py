"""HTTP acquisition. Conservative: explicit timeout, few retries, size cap."""

from __future__ import annotations

import logging
import time

import httpx

from psd2_kpi_es import config
from psd2_kpi_es.acquisition import rawstore
from psd2_kpi_es.errors import NetworkError, SourceNotFoundError, UnsupportedFormatError

log = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_BACKOFF_S = 2.0
POLITE_DELAY_S = 1.0  # minimum delay between requests to the same host


def _filename_from(url: str, content_type: str | None) -> str:
    name = url.rstrip("/").rsplit("/", 1)[-1] or "index"
    if "." not in name:
        ext = {
            "application/pdf": ".pdf",
            "text/html": ".html",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        }.get((content_type or "").split(";")[0], ".bin")
        name += ext
    return name


def fetch_url(client: httpx.Client, url: str) -> tuple[bytes, httpx.Response]:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = client.get(url, follow_redirects=True)
            if resp.status_code == 404:
                raise SourceNotFoundError(f"404 for {url}")
            resp.raise_for_status()
            if len(resp.content) > config.MAX_ARTIFACT_BYTES:
                raise UnsupportedFormatError(
                    f"artifact exceeds {config.MAX_ARTIFACT_BYTES} bytes: {url}"
                )
            return resp.content, resp
        except httpx.HTTPStatusError:
            raise
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    raise NetworkError(f"failed to fetch {url}: {last_exc}")


def fetch_and_store(client: httpx.Client, entity_id: str, url: str) -> rawstore.RetrievalEvent:
    log.info("fetch %s %s", entity_id, url)
    try:
        content, resp = fetch_url(client, url)
    except Exception as exc:
        event = rawstore.record_fetch(
            entity_id,
            url,
            content=None,
            http_status=getattr(getattr(exc, "response", None), "status_code", None)
            or (404 if exc.__class__.__name__ == "SourceNotFoundError" else None),
            content_type=None,
            error=f"{exc.__class__.__name__}: {exc}",
        )
        raise
    ctype = resp.headers.get("content-type")
    event = rawstore.record_fetch(
        entity_id,
        url,
        content=content,
        http_status=resp.status_code,
        content_type=ctype,
        filename=_filename_from(url, ctype),
    )
    log.info("stored %s sha256=%s bytes=%d", entity_id, event.sha256, event.bytes)
    return event


def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=config.REQUEST_TIMEOUT_S,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        },
    )
