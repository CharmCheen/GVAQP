# SD-AQP: Self-Diagnosing Adaptive AQP

Date: 2026-07-03

## Problem

`toy_simulation_gate_v2` showed that the previous full planner was not acceptable:

- It improved prior-wrong aggregate missing mass, but still left high missing mass.
- It damaged strong-prior settings relative to top-prior-only.
- Its Phi upper bound covered true missing mass only because the bound was too loose.
- Its dual-ledger check was structural, not a tight statistical validity proof.

## Algorithm Sketch

SD-AQP splits oracle calls into three ledgers:

- DISCOVER ledger: used to return positives and diagnose whether the cheap prior is trustworthy.
- AUDIT ledger: the only ledger used by the stratified `M_hat` estimator.
- REPAIR ledger: local expansion around discovered positives, governed by a Beta posterior hit-rate model.

The first `trust_probe_calls` are high-prior DISCOVER calls. Their observed hit rate is a cheap, online prior-trust test:

- If hit rate >= `trust_hit_rate_threshold`, SD-AQP preserves the strong prior and continues top-prior selection.
- Otherwise it switches to AUDIT + REPAIR. AUDIT keeps estimator separation; REPAIR is enabled only when its Beta upper-mean bid beats the next prior DISCOVER bid.

This is not a formal certificate. The goal is an empirical control policy that avoids the v2 strong-prior regression while preserving prior-wrong recovery.

## Intended Novelty

The potentially publishable idea is not "use top-k plus repair"; it is the self-diagnosing control loop:

1. A discovery-ledger prior-trust test chooses whether to trust or override the cheap prior.
2. A separate audit-ledger estimator tracks missing mass without contamination from adaptive discoveries.
3. A repair ledger learns local cluster validity with a Beta posterior and is automatically suppressed when clusters are absent.
4. The policy explicitly refuses to use loose Phi upper bounds for stopping until bound-width diagnostics pass.

## Current Status

This is an exploratory v3 candidate. It must pass strict synthetic gates before any real-video oracle work.
