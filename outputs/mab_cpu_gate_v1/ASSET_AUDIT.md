# ASSET_AUDIT — CPU-only MAB gate, Phase 0

Date: 2026-08-13. Mode: static inventory + deterministic reconstruction. No inference.

## Summary

- Core artifacts present: 12; absent (recorded hashes only): 7.
- The P1/P2 pipeline's five substrate parquet tables are **not in this checkout**
  (consistent with provenance/omitted_legacy_manifest.csv: `*.parquet` = D_BULK_RESULT).
- However, two full substrates ARE locally reconstructible deterministically from
  frozen raw artifacts:
  1. **Q_VULNERABLE full 1475-unit semantic table** <- qwen32_oracle/raw/*.json
     (264 relevant / 1207 not_relevant / 4 parse_failure).
  2. **Proxy A (V3 YOLO) per-unit scores** <- raw_unit_detections.jsonl via the
     frozen scoring function `0.5*min(det_count,20)/20 + 0.5*max_conf`;
     per-video min/mean/max validated against PROXY_REGIME_MANIFEST R0 rows to 1e-9.

## Hard limits (declared, not guessed)

1. **No 2s/5s semantic outcomes exist anywhere locally**; the model-relative
   reference itself is 10s-quantized -> multi-granularity action value is
   BLOCKED_GPU_MULTIGRANULARITY; only geometric/granularity-ceiling analysis
   is possible (Phase 1).
2. **Q_DRIVER full grid is unrecoverable** (seal raw = 21/1475 units; the
   FINAL_UNIT_REFERENCE.parquet sha256 4f732859... is recorded but the file is
   absent). Q_DRIVER analysis below uses the union of trace-queried labels
   (283-333 units/cluster) and is marked MODEL_RELATIVE_DIAGNOSTIC_ONLY with a
   PARTIAL reference reconstructed from known positives only.
3. **Proxy B per-unit scores are NOT_AVAILABLE** (parquet absent; optical-flow
   scores not reconstructible from YOLO detections). Proxy B remains usable
   only through the P2 trace corpus as a policy-order source, not as features.
4. **Costs**: no local wall-clock VERIFY cost profile exists; the gate uses
   abstract query-count budgets (5..100) with cost sensitivity notes.
   Physical SCAN costs from the blocked pilot (warm median ~1.18-1.21 s) and a
   few Guangzhou VERIFY durations (~8-10 s) exist but are single-source and
   marked exploratory.
5. **Human reference: 0 labels** (P1 frozen, unread). All values below are
   MODEL_RELATIVE_DIAGNOSTIC_ONLY. Final decision records
   BLOCKED_INDEPENDENT_REFERENCE for human-event claims.

## Fidelity anchor

scripts/mab_cpu_gate/validate_engine.py: C1 materializer + strict-overlap 1:1
matching reproduce P2 TRACE_MANIFEST EventF1/TP/FP/FN for all 252
Q_VULNERABLE rows with **0 mismatches** (reference: 55/50/32 events for
DALI/HANGZHOU/WUHAN from 127/84/53 positives).
