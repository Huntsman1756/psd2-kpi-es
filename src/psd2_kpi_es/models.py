"""Canonical data model for psd2-kpi-es.

Schema version 1. Any breaking change to Observation/Source fields must bump
DATASET_SCHEMA_VERSION and be documented in the changelog.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATASET_SCHEMA_VERSION = 1


class PeriodType(StrEnum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    UNKNOWN = "unknown"


class InterfaceType(StrEnum):
    DEDICATED_API = "dedicated_api"
    WEB = "web"
    MOBILE = "mobile"
    PSU_INTERFACE = "psu_interface"  # generic/other PSU-facing channel
    OTHER = "other"
    UNKNOWN = "unknown"


class Service(StrEnum):
    AIS = "AIS"
    PIS = "PIS"
    PIISP = "PIISP"  # also called CBPII / FCS by some publishers
    ALL = "ALL"
    UNKNOWN = "UNKNOWN"


class Metric(StrEnum):
    AVAILABILITY = "availability"
    DOWNTIME = "downtime"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    REQUEST_SUCCESS_RATE = "request_success_rate"
    REQUEST_COUNT = "request_count"
    OTHER = "other"


class Unit(StrEnum):
    PERCENT = "percent"
    MS = "ms"
    SECONDS = "seconds"
    COUNT = "count"
    RATIO = "ratio"
    OTHER = "other"


class Aggregation(StrEnum):
    """How the reported value was produced by the publisher."""

    DAILY_MEAN = "daily_mean"  # mean over the day (typical TMR/TMD)
    MEAN = "mean"
    SUM = "sum"
    POINT = "point"  # value for the period as a whole / single measurement
    UNKNOWN = "unknown"


class ValueStatus(StrEnum):
    REPORTED = "reported"
    NOT_REPORTED = "not_reported"  # publisher left the cell blank / "NP"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"


class Comparability(StrEnum):
    DIRECT = "DIRECT"  # same publisher, same declared methodology
    PARTIAL = "PARTIAL"  # aligned definition but publisher-specific methodology
    NOT_COMPARABLE = "NOT_COMPARABLE"
    UNKNOWN = "UNKNOWN"


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    legal_name: str
    brand_name: str
    country: str = "ES"
    website: str | None = None
    lei: str | None = None


class SourceDocument(BaseModel):
    """An index or document endpoint declared in the catalog."""

    model_config = ConfigDict(frozen=True)

    kind: str  # "index" (page listing documents) or "document"
    url: str
    parser: str
    notes: str | None = None


class SourceArtifact(BaseModel):
    """One fetched artifact, identified by its content hash.

    If a URL changes content, a new SourceArtifact row is created; the old one
    is preserved. Same content re-fetched => same sha256, new retrieval event.
    """

    source_id: str  # sha256 hex digest of content
    entity_id: str
    source_url: str
    retrieved_at: datetime  # first time this exact content was fetched
    http_status: int | None = None
    content_type: str | None = None
    filename: str | None = None
    sha256: str
    bytes: int
    published_at: date | None = None  # when the publisher says it covers/was issued
    period_hint: str | None = None
    parser_name: str
    parser_version: str

    @staticmethod
    def make_id(sha256: str) -> str:
        return f"src_{sha256[:16]}"


class Observation(BaseModel):
    """One normalized metric value extracted from a source artifact."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    entity_name: str

    period_start: date
    period_end: date
    period_type: PeriodType
    period_label: str  # e.g. "2025Q3", "2025-10-01", "2025-10"

    interface_type: InterfaceType
    service: Service

    metric: Metric
    value: float | None  # None when value_status != reported
    unit: Unit
    aggregation: Aggregation
    value_status: ValueStatus = ValueStatus.REPORTED

    metric_definition: str | None = None
    metric_definition_url: str | None = None

    comparability: Comparability
    comparability_group: str

    source_id: str
    source_url: str
    source_document: str | None = None  # e.g. page/sheet locator inside artifact

    published_at: date | None = None
    retrieved_at: datetime | None = None
    source_sha256: str

    parser_name: str
    parser_version: str

    raw_label: str | None = None
    raw_value: str | None = None
    raw_unit: str | None = None

    # "verbatim": the normalized value is the published cell parsed as
    # documented. "inferred": the value required a documented interpretation
    # (e.g. unit inconsistent with magnitudes, corrupted glyph recovery).
    interpretation: Literal["verbatim", "inferred"] = "verbatim"

    notes: str | None = None

    @property
    def observation_id(self) -> str:
        """Deterministic id derived from the logical key of the observation."""
        key = "|".join(
            [
                self.source_sha256,
                self.entity_id,
                self.period_label,
                self.interface_type.value,
                self.service.value,
                self.metric.value,
                self.raw_label or "",
            ]
        )
        return "obs_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


class ParseWarning(BaseModel):
    code: str
    message: str
    context: str | None = None


class ParseResult(BaseModel):
    observations: list[Observation] = Field(default_factory=list)
    warnings: list[ParseWarning] = Field(default_factory=list)
