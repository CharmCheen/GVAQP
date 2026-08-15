# PROVENANCE.md — CPU-only MAB gate

Date: 2026-08-13. Machine: CPU-only macOS checkout `/Users/charmcheen/FDU/入学前/GVAQP`.
No GPU, no model inference, no downloads, no human labels read.

## Inputs (all frozen repository artifacts; hashes)
- frozen_unit_grid_v1.csv (10s unit grid, 1475 units)
- qwen32_oracle/raw/*.json (1475 unit outcomes, Q_VULNERABLE; label table
  reconstructed from raw records, validated 252/252 vs P2 TRACE_MANIFEST)
- v3_scan_proxy_preregistration_v1/frozen_raw/*/raw_unit_detections.jsonl
  (Proxy A scores reconstructed with frozen scoring fn
   0.5*min(det_count,20)/20+0.5*max_conf; per-video min/mean/max validated
   1e-9 vs PROXY_REGIME_MANIFEST R0)
- p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv (504 frozen trace rows)
- p0_materializer_validation_v3/controlled_pairs.csv, seals (Q_DRIVER partial)
- Absent (recorded hashes only): proxy_table/candidate_table/FINAL_UNIT_REFERENCE/
  P1_QWEN32_UNIT_OUTCOMES/PROXY_B parquets; 2s/5s semantic outcomes; human labels (0 rows).

## Reconstructions (deterministic, validated)
- Q_VULNERABLE full-grid C1 reference: 55/50/32 events (DALI/HANGZHOU/WUHAN)
  from 127/84/53 positives; reproduces P2 EventF1/TP/FP/FN exactly (252/252).
- Proxy A per-unit scores: reconstructed + validated.

## Execution log (this run)
- validate_engine.py: 252/252 mismatches=0
- phase0_assets.py -> ASSET_MANIFEST.csv (19 rows), ASSET_AUDIT.md
- phase1_granularity.py -> GRANULARITY_PHASE_DIAGRAM.csv/md
  (GEOMETRIC_CEILING_ONLY; G_granularity semantic = NOT_ESTIMABLE)
- phase2_action_table.py -> ACTION_VALUE_TABLE.parquet
  (rows: see table; sampling check: abs error 0.0 in all checked states)
- phase3_gate_metrics.py -> MAB_GATE_METRICS.json/csv
- phase4_mab_v0.py -> MAB_V0_RESULTS.csv (or NO_RUN stub)
- pytest tests/mab_cpu_gate: see FINAL_DECISION.md section 8

## Scope declarations (hard)
- FIXED_CANDIDATE_REPLAY only; no REAL_ENDOGENOUS_ACQUISITION conclusions.
- MODEL_RELATIVE_DIAGNOSTIC_ONLY; BLOCKED_INDEPENDENT_REFERENCE for human claims.
- Abstract query-count budgets (5..100); no wall-clock deadline claim.
- Statistical unit: video x query. Seeds are Monte-Carlo variance only.
