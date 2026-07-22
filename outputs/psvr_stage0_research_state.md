# PSVR Research State — Superseded Stage 0 Snapshot

## Authoritative current state

- `ORACLE_REFERENCE_INTEGRITY = PASS`
- `RUNTIME_CAPABILITY_ISOLATION = PASS`
- `COLD_PROCESS_COLD_PROXY_REGIME = NO_GO`
- `WARM_ORACLE_COLD_PROXY_REGIME = GO`
- `PSVR_PHYSICAL_SMOKE_TEST = FAIL`

The active workload is warm-oracle/cold-proxy: Qwen is resident while proxy evidence is absent. This remains a partial-proxy workload.

## Active hypothesis

H-DS1: a workload-matched complete-path tail bound plus independent durable-commit reservation can eliminate deadline misses without eliminating all T_mid utility.

## Rejected hypotheses

- The legacy frozen runner is leakage-safe.
- Independent operator p95 values plus one second form a hard-deadline guarantee.
- Strict cold-process initialization permits a useful partial-proxy interval on this hardware.

## Permanent failure evidence

T_short Coverage-Interleave admitted VERIFY and committed at 35.663871 s, missing the final approximate 30.829949 s deadline by 4.833922 s. The 21.436421-second physical VERIFY sample remains in the raw ledger.

## Current action

Deadline safety only: exact ledger instrumentation, tail-aware guard tests, workload-matched complete-path profiling, ten physical T_short validations, and a small T_mid utility regression. The machine-readable authoritative state is `outputs/psvr_autonomous_research/RESEARCH_STATE.json`.
