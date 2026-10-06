"""Typed error codes. Fail loudly instead of emitting silent nulls."""

from __future__ import annotations


class Psd2Error(Exception):
    code = "INTERNAL_ERROR"


class NetworkError(Psd2Error):
    code = "NETWORK_ERROR"


class SourceNotFoundError(Psd2Error):
    code = "SOURCE_NOT_FOUND"


class SourceChangedError(Psd2Error):
    code = "SOURCE_CHANGED"


class UnsupportedFormatError(Psd2Error):
    code = "UNSUPPORTED_FORMAT"


class ParseError(Psd2Error):
    code = "PARSE_ERROR"


class ValidationError(Psd2Error):
    code = "VALIDATION_ERROR"


class SemanticAmbiguityError(Psd2Error):
    code = "SEMANTIC_AMBIGUITY"
