# ADR-003: Comparability modeled per observation

## Status: accepted (v0.1)

## Context
Same-looking metrics differ semantically across banks (% Éxito vs % Éxito
consolidación; seconds vs mislabeled-milliseconds; per-service vs
interface-wide availability).

## Decision
Each observation carries `comparability` + `comparability_group`. CLI
`rank --comparable-only` refuses multi-group result sets; `compare` warns.
Cross-entity quarter comparisons aggregate daily values uniformly and mark
published-aggregate fallbacks visibly.

## Consequences
+ Methodologically unsafe rankings are blocked, not just warned.
− Some queries need an explicit group choice; documented in
  docs/comparability.md.
