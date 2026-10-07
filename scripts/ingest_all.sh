#!/usr/bin/env bash
# Per-entity ingest with outcome tracking.
#
# `psd2-kpi-es ingest` exits 5 with a typed {"error_code": ...} JSON on
# stderr for domain failures:
#   - SOURCE_NOT_FOUND is an expected, modelled absence (a publisher may
#     legitimately retire an endpoint) — reported, not fatal.
#   - Any other error (network, parse, validation) is a real ingestion
#     failure. A successful run that produced zero observations is treated
#     as a failure too (every parser failed).
# Exits non-zero if any entity has a real failure; writes a summary to
# $GITHUB_STEP_SUMMARY when present.

set -u

ENTITIES="${ENTITIES:-renta4 unicaja caixabank santander}"

failed=""
missing=""
empty=""

for e in $ENTITIES; do
    echo "=== ingest $e ==="
    out="$(mktemp)"; err="$(mktemp)"
    if uv run psd2-kpi-es ingest "$e" >"$out" 2>"$err"; then
        cat "$out"
        sed 's/^/  [stderr] /' "$err" >&2
        obs="$(jq -r '.observations // 0' <"$out")"
        if [ "$obs" = "0" ]; then empty="$empty $e"; fi
    else
        rc=$?
        cat "$out"
        sed 's/^/  [stderr] /' "$err" >&2
        code="$(grep -m1 '^{"entity"' "$err" | jq -r '.error_code // empty' || true)"
        if [ "$code" = "SOURCE_NOT_FOUND" ]; then
            missing="$missing $e"
        else
            failed="$failed $e(rc=$rc${code:+,code=$code})"
        fi
    fi
    rm -f "$out" "$err"
done

{
    echo "### Ingest results"
    echo "- real failures:${failed:- none}"
    echo "- source not found (modelled):${missing:- none}"
    echo "- zero observations:${empty:- none}"
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

if [ -n "$failed" ] || [ -n "$empty" ]; then
    echo "ingest failures:${failed}${empty}" >&2
    exit 1
fi
