# PSTR proxy provenance audit

PSTR uses the proxy column already supplied to the ARC adapter within each domain. It does not use oracle labels or event references to compute that column. The five retrospective domains use three historical cheap-proxy pipelines.

## dataset3

- PSTR input: `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/public_proxy.csv`.
- Input SHA-256: `7edd7fc87f849ce9f32bb26edc368aaf986952100c3f2184cd95cef015c33815`.
- Selected field: normalized `score_fusion_yolo_motion`, the same primary proxy chosen by the controlled ARC benchmark.
- Immediate feature source: `benchmark/proxy_precompute/full/center10_proxy_features.csv`.
- Feature-source SHA-256: `b84b34b83de5e9f6263cd12e63f95c0b8c79c59e85e7671d5de50b0c933dcdec`.
- Model: `yolov8n.pt`, SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.

The frozen proxy table contains only public proxy values and provenance fields. Unit IDs cover exactly `0..346`; PSTR uses those IDs as temporal order.

## realcartest 2000–3200

- PSTR input: `outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv`, field `proxy_score`.
- Adapter SHA-256: `6ca8c9eebc8b5808abd933879cca3890bda799128ac9e0911ebfc988591d66bf`.
- Immediate source: `outputs/exsample_aware_replay/atomic_grid_10s.csv`, field `prior_score_max`.
- Atomic-grid SHA-256: `bd0e6ee8eac9e44a8987d5e6df7b4fd4d5adbccdeb8bf132cf91f21cbd5a6afc`.
- Cheap-signal source: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv`, field `cheap_fused_score`.
- Cheap-signal SHA-256: `5a58a80010fd3f1eaee2ae88011ce48c5f50e4265320c42444ed93524c12a1ff`.
- Construction: maximum `cheap_fused_score` across the five two-second subunits in each ten-second bin.

The cheap-signal table has 22 public feature/score fields and no oracle label or event-ID field. The 120 adapter proxy values equal the 120 atomic-grid values exactly (`max_abs_error = 0`).

## realcartest 0–1570, 1630–2000, and 3200–3830

- Cheap-proxy source: `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv`, field `score_count`.
- Source SHA-256: `573af538d39c2e8ad7cdc6c461f50104acd8f6b4829210064a507120286c18f8`.
- Construction: maximum `score_count` among retained cheap-proxy clips whose time interval overlaps each ten-second bin.
- Grid hashes:
  - 0–1570: `5fe80a5b4b8d0c02f0d41a301cd78af186b5ba696b2fd63eebcc43b8015fc0f7`
  - 1630–2000: `2fd09a701ad7db199536a9e202411fb4f00c095b7c5d4eee4397820c58fc61cb`
  - 3200–3830: `1dfacb84a43f06235e7c501c7b6eef8afa8379871ca0abe534a66084890add1f`

Recomputing all 257 grid values from the hashed RoadCLIP proxy file gives exact equality (`max_abs_error = 0`).

## Interpretation limit

Within each domain, PSTR, pure proxy top-k, and ARC exact-fill use the same proxy values, so selector comparisons are input-fair. Across domains, the proxy generator is not held fixed. The evidence supports temporal stratification as a candidate wrapper around an available public proxy; it does not establish invariance to proxy construction. A future external gate must freeze its proxy pipeline and bytes before labels are opened.
