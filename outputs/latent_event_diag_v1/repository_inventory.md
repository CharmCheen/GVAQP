# Repository Inventory

Audit basis: executable code, CLI construction, CSV schemas/content, and output hashes. Markdown-only claims are not marked verified.

| Component | Actual implementation path | Entry point | Config source | Existing artifacts | Verified status | Risk |
|---|---|---|---|---|---|---|
| K3 BB-EM | `scripts/stage0_7_minimal_operator_compression.py` | `construct_k_segments` and CLI `main` | hard-coded `PARAMS(g_max=1,d_core_max=40,D_seg_max=60,E=1)`; YAML is written from constants | `outputs/stage_0_7_minimal_operator_compression/{segments,metrics_by_run.csv,data_manifest}` | VERIFIED | all `oracle_label==0` are hard barriers; relation semantics absent |
| C6 materializer | `scripts/stage0_6_materializer_ablation.py` | `construct_variant_segments` | hard-coded `PARAMS`; `RULES` map | `outputs/stage_0_6_materializer_ablation/segments` | VERIFIED | raw trigger counts overlap earlier blockers |
| K3 evaluator | `scripts/stage0_merge_only_repair.py` | `evaluate_segments`, `greedy_matches` | overlap-any and tIoU thresholds in code | Stage 0.6/0.7 metrics and per-segment results | VERIFIED | greedy rather than globally optimal matching; aggregate metrics mask boundary/hash differences |
| MAP-anchor-only | `scripts/stage1a_map_anchor_only.py` | `simulate_map`, CLI `main` | q0.70 proxy threshold, 60s audit window, 80/20 or 70/30 split in code | `outputs/stage_1a_map_anchor_only/{oracle_logs,component_tables,segments}` | VERIFIED | `seed` is metadata-only; deterministic repeats are not stochastic evidence |
| MAP barrier | `scripts/stage1b_map_anchor_barrier.py` | `simulate_map_anchor_barrier` | high-budget 60/20/20 quotas in code/YAML | `outputs/stage_1b_map_anchor_barrier/{action_traces,barrier_candidates,segments}` | VERIFIED | PLACE_BARRIER produces the same binary label consumed by K3; no typed distinction |
| SUPG adapter | `refe_repos/adapter/supg_baseline/run.py` | `run_selection`, CLI `main` | CLI defaults (`target_recall=.9`, `mixing_eps=.1`, seed) | paired all-selected/confirmed-only logs and segments | VERIFIED | native selected sets are erased by K3 input projection |
| ABae adapter | `refe_repos/adapter/abae_baseline/run.py` | `run_abae`, CLI `main` | proxy strata=5; budget-derived pilot; seed | per-budget/seed logs and segments | VERIFIED | ABae-inspired aggregation allocation is adapted to discovery |
| ARC adapter | `refe_repos/adapter/arc_baseline/run.py` | `run_refinement`, native `original_arc` | threshold sweep .1-.5, `each_frame`, CLI seed | native segments/oracle logs; Stage 1A diagnostic | VERIFIED | K3 rematerialization discards ARC native candidate boundaries |
| Shared adapter merge/eval | `refe_repos/adapter/common.py` | `selected_units_to_segments`, `evaluate_segments` | merge gap and IoU CLI config | native `audit_metrics.csv` files | VERIFIED | native adapter evaluator differs from later overlap-any evaluator |
| Unit/evidence table | `outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv` | CSV replay input | artifact schema | 120 rows, 1 video; proxy, binary oracle label, 10s boundaries | VERIFIED | GT/VLM provenance is not encoded per observation; no typed relation or multiplicity |
| Event reference table | `outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv` | evaluator input | artifact schema | 20 rows with `source_event_id`, interval and event type | VERIFIED | no canonical-anchor field and no actor identity |
| Ordered query logs | `outputs/ours_vs_baselines_realcartest_v1/*_outputs/*/oracle_log.csv` | `call_idx` | baseline-specific selectors | Stage 0.7 manifest: 270 included runs; ordered call schemas verified | VERIFIED | binary labels cannot identify SAME versus DISTINCT |
| Matching outputs | Stage 0.6/0.7 `metrics_by_run.csv` and segment files | overlap-any/tIoU evaluation | code constants | 1,944 Stage 0.7 metric rows | VERIFIED | no canonical-anchor matching artifact exists |
| uniform/random/top-proxy shared replay | not located in audited realcartest comparison | none verified | unknown | no common per-budget logs/segments | BLOCKED_BY_MISSING_ARTIFACT | cannot audit event_merge sharing or SEHS leakage |
| New diagnostic scaffold | `src/garc_eval/latent_event_diag/` | `experiment`, `audit` modules | explicit dataclass configs and seeds | this output directory | VERIFIED by tests | synthetic only; not a real-data conclusion |

## Existing Evaluation Semantics

- `overlap_any`: temporal intersection greater than zero, then greedy one-to-one matching.
- tIoU: evaluated at 0.1/0.3/0.5 with the same greedy matching.
- precision/recall/F1: counts matched predictions/references.
- returned seconds: existing reports call this total predicted duration/overcoverage; the new scaffold exposes `returned_seconds` directly.
- overmerge: existing `overmerge_multiplicity` is mean number of references overlapped per prediction.
- oversplit: existing Stage 0.6 extra metrics expose segments per reference; the new scaffold exposes an explicit rate.
- canonical-anchor matching: not found in the audited real-data code/artifacts; implemented only in the new diagnostic evaluator.

## State Protection

The initial worktree already contained a modified empty `AGENTS.md` and many untracked Stage 0-2 files/output directories. None were changed. A Git `safe.directory` entry was required to read repository state.
