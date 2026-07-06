# Bug Fix Summary

## Problem

`discovery_d3_chunk_bandit` in `run_event_diverse_discovery.py` ignored the `queried` argument. This caused audit/repair/guard calls to be excluded from the chunk-bandit state and allowed discovery to re-query already-queried bins.

## Fix

In this experiment we use a corrected version of `discovery_d3_chunk_bandit` that:

1. Initializes `n_c`, `sample_count`, and `N1_c` from the incoming `queried` set.
2. Treats all `queried` bins as unavailable for selection (no re-query).
3. Keeps Thompson sampling, Gamma parameters, chunk size, and within-chunk uniform sampling unchanged.

## Scope

Only the D3 chunk-bandit discovery accounting is changed. No other algorithm component (repair trigger, repair expansion, Core/Halo release, prior score, budget grid) is modified.
