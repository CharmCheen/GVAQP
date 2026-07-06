# Diagnosis Data Gap Report

## What was missing in the existing outputs

The existing `event_diverse_frontier_raw.csv` only reports aggregate per-trial metrics (precision/recall, call counts, unique event counts). It does **not** contain:

- The order of individual oracle calls (audit → repair → discovery → guard).
- The bin/chunk/time/label of each call.
- The chunk-bandit state (n_c, N1_c, expected theta) at each decision point.
- Whether a discovery call re-queried a bin already queried by audit/repair/guard.

## How the gap was filled

We re-ran `D3-core-chunk120` and `D3-norepair-core-chunk120` using the **same labels** (no new oracle/VLM calls) with an instrumented wrapper that logs every call and the bandit state. The wrapper copies the exact algorithm logic from the existing code and only adds logging.

This is a diagnostic replay, not a new experiment or new label collection.
