# Hybrid Cold-Start Discovery Design

## Motivation

The diagnosis showed that discovery-only v2 loses to B6 at B=10/20 because prior-score ranking is not spatially diverse: it can spend multiple low-budget calls on the same event. B6's chunk-level Thompson sampling spreads calls across chunks and therefore discovers new events faster.

## Algorithm

For budgets B <= 20 (the cold_start_fallback regime):

1. **Phase 1 (chunk exploration)**: allocate `phase1_calls = min(chunk_count, ceil(B * r))` calls to B6-style chunk-level Thompson sampling. This seeds the search with spatially dispersed bins.
2. **Phase 2 (prior exploitation)**: use the remaining `B - phase1_calls` calls to select the highest-prior unqueried bins, exactly as v2 discovery does.

For B > 20, hybrid is **not applied** because cold_start_fallback is not active; the method falls back to the existing v1 audit/discovery/repair path.

## Parameters

- `r` (phase-1 fraction): default/final value **0.5**.
- `chunk_size_s`: 120 s, identical to B6.
- `chunk_count`: `ceil(n_bins / (chunk_size_s / bin_size))`.

## Hard-constraint compliance

- No segment- or event-specific rules.
- No GPU/VLM/new labels.
- The only new parameter is `r`, evaluated at {0.3, 0.5, 0.7} and selected by a pre-specified criterion.
