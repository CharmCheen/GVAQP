# A800/A100 Numerical Equivalence Report

`A100_INPUT_REPRODUCIBLE = true`

`A100_MIXING_COMPATIBLE = NOT_ESTABLISHED_NOT_NEEDED`

`VALID_A800_RESULTS_MIXED = 0`

Fixed frozen Suite A and B settings at seed `2026071100` were compared. The mechanism uses NumPy/SciPy CPU only; no Torch/CUDA API occurs in generation, policy, materialization, or metrics. Persisted A800 public inputs reproduce exactly, and Suite A's persisted hidden timeline reproduces exactly. Query sequences, action types, outcomes, and metrics demonstrate deterministic replay under the current CPU code; they are not direct comparisons to durable A800 policy traces because no such traces exist.

Rows: 78; pass: 78; fail: 0. Discrete and deterministic arrays require exact identity; metric tolerance is `1e-12`. Tie-breaking was exact.

Limitation: B_COUNTERFACTUAL hidden A800 buffer unavailable; inferred from exact joint-RNG public arrays and CPU-only path.. Full A800/A100 policy-execution equivalence is therefore not established. This does not authorize mixing, and no A800 setting is accepted as complete or mixed into final results. All canonical outputs are computed on one A100-host CPU path. No policy logic was changed.
