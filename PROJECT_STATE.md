# SQ-CRAQ Project State

Last updated: 2026-07-07

## Current Stage

**Limited-oracle temporal event retrieval / LATE-AQP frontier.**
We have completed the first executable LATE-AQP pipeline (audit + discovery + repair + boundary guard + Core/Halo release) and validated it under strict limited-oracle replay across six segments of two videos (`realcartest`, `dataset3`). The pipeline reaches 90/90 event precision/recall on every qualified segment at the practical budget cap (B<=120), and the strongest current empirical baselines are **B7-core** and **D3-norepair-core** (chunk-bandit discovery, no repair, Core/Halo release). Core/Halo has been shown to be a **generic post-processing gain** that lifts B6/B7 to the same 90/90 frontier as LATE-AQP-core; the LATE-specific advantage over these release-augmented baselines is **not established** for performance alone.

**Two-track situation.** Two parallel experimental tracks coexist in this repo:

1. **LATE-AQP track** (`outputs/late_aqp_*`): nine features operationalized end-to-end (core/halo release, boundary guard with budget accounting, temporal merge, duplicate suppression, duration cap, abstain via `p_answer`, 4-way budget accounting, per-interval lineage logging, halo diagnostics). Validated on realcartest (3 segments) and dataset3 (3 segments) at budgets 5-120. All oracle-relative to VLM labels.

2. **Phase 3 selector smoke track** (`outputs/agent_loop_v1/phase3_selector_smoke_v1/`): a separate cheap-signal -> simple selector -> NMS -> budgeted return-set experiment on the smaller `dataset3` `probe_set_v1` scope. **Result: completed_negative** — at B=40, uniform_random reaches event_recall_iou_0_3 = 0.153 (50 seeds), the best deterministic cheap-signal selector reaches 0.050. This is the empirical motivation for the next redesign step (T010, see `TASK_QUEUE.yaml`).

The two tracks share the cheap-signal feature tables but use different reference labels and different selection/release code; they are not directly comparable on the same numbers.

## Active Conclusions (oracle-relative to VLM labels; not human ground truth, not formal guarantees)

- **EventLift-discover-certify (DC) is the strongest supported EventLift variant.** Source: `EVENTLIFT_FULL_BENCHMARK_V1_REPORT.md`, `EVENTLIFT_RESULTS_SYNTHESIS.md`. Across 486 strict-replay runs (9 methods × 6 segments × 3 budgets × 3 seeds, 0 budget violations, 0 event_id online leaks), EventLift-DC achieves the highest macro recall (0.156) at budget 0.30 among strict_replay methods; CERTIFY improves precision on 4/6 segments and recall on 2/6 without hurting recall anywhere. AUDIT fires only on dev segment (17/36 calls); SUPPRESS never fires; safe stopping not claimed (all 486 runs abstain). B7-strict-replay is the fair B7 comparison; B7-core-posthoc is context-only.
- **Proxy bias is the dominant failure mode on dataset3 segments.** Source: `PROXY_BIAS_DR_FEASIBILITY.md`, `outputs/eventlift_dr_feasibility/proxy_calibration_by_segment.csv`. Per-segment proxy AUC: realcartest 0.68-0.78; dataset3 0.31-0.56. On dataset3_0_1200 all 7 positive bins sit in the bottom 50% of proxy bins (AUC = 0.31) — proxy guidance is actively anti-informative. DR / AIPW audit-correction feasibility: Gate A = PASS, Gate B = CONDITIONAL (deployable per-stratum-LOO p_model gives ≥20% RMSE reduction on 1/6 segments — dataset3_0_1200; the aggregate ≥4/6 only emerges under a raw-minmax strawman), Gate C = PASS border-line. EventLift-DR has not been implemented; pre-implementation feasibility only; DR/AIPW is a known estimator family.
- **HTS-AQP hierarchical tree search has segment-dependent upper-bound feasibility.** Source: `outputs/hts_aqp_phase0_feasibility/HTS_PHASE0_FEASIBILITY_REPORT.md`, `HTS_AQP_DESIGN.md`. God's-eye deterministic coarse-to-fine at b=4 saves 21-59% calls vs flat scan on dataset3 segments; full-coverage call count = 49-171 calls/segment where no strict_replay baseline reaches that coverage at any available budget. realcartest_2000_3200 shows regression (b=2 −20.8%, b=4 −0.8%) due to coarse-positive saturation. Verdict = **B (weakly feasible / segment-dependent)**. HTS is a known hierarchical search paradigm; Phase 0 uses `any-overlap` coverage convention (diagnostic-only), while baselines use IoU ≥ 0.3; Phase 0 coverage numbers are upper bounds, not performance claims. Coarse-oracle-VLM-reliability assumption unvalidated.
- **HTS-EC saturation-aware gated dual frontier passes God's-eye feasibility (Gate C v2 = PASS).** Source: `HTS_EC_DELTA_AND_FEASIBILITY.md`, `outputs/hts_ec_feasibility_v1/tree_upper_bound_v2.csv`. Gate decision upgraded from B to A. `HTS_EC_dual_frontier_gated` passes all 4 conditions under God's-eye simulation: rc_2000 recall=0.250 (beats flat 0.200 by +0.050), sparse savings preserved (ds3_0_1200=0.167, ds3_1200_2400=0.083, ds3_2400_3462=0.222). Key design: theoretical break-even density d*≈0.245 (no labels, no circularity), Beta-posterior detector (P(d≥d*)>0.75, k_min=5), gated dual frontier (fine bins activated only when detector triggers, then tree+fine compete). **CAVEAT: God's-eye simulation only — drill/prune uses full labels. Strict-replay implementation (posterior-based drill/prune) is the next step; v2 results are upper bounds on strict-replay performance.** The claim "HTS-EC fixes dense regression" is supported under God's-eye only, NOT yet under strict replay.
- **Core/Halo is generic.** B6-core and B7-core reach 90/90 on the same segments as LATE-AQP-core. Source: `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md` and `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md` Q10. Treat Core/Halo release as a **generic release module**, not a LATE-specific advantage.
- **Repair marginal value is neutral after the D3 accounting fix.** `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md` reports the chunk-bandit `queried`-state bug reduced D3-core mean duplicates from 11.21 to 0.51 (95.4% reduction); post-fix, D3-core-fixed is **not** consistently better than D3-norepair-core. Repair is no longer argued to be net-positive on the chunk-bandit discovery backbone. **Recommended next D3 variant: D3-norepair-core.**
- **LATE-D1/D2/D3 do not beat B7-core.** None of the new event-diverse discovery policies (D1 temporal-NMS prior, D2 component proposals, D3 chunk-bandit) achieves a strictly lower B_90/90 than B7-core on any of 6 segments. Source: `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4. **Strongest current empirical baseline: B7-core (with D3-norepair-core as the strict-replay alternative).**
- **The dominant low-budget failure is upstream discovery miss.** Limited-oracle frontier failure taxonomy: 6 discovery_miss vs 6 release_over_conservative vs 3 LATE-specific. Source: `outputs/late_aqp_limited_oracle_frontier_v1/failure_taxonomy.csv`. Core/Halo is already effective when discovery finds the events; improving upstream discovery is the open lever.
- **Phase 3 fixed cheap-signal selector is negative.** Source: `outputs/agent_loop_v1/phase3_selector_smoke_v1/phase3_selector_smoke_report.md`. The current deterministic cheap-signal selectors do not convert signal-level diagnostics into better budgeted return-set coverage.
- **Frozen v2 cold-start fix is split-validated, not re-validated on the original failure segments.** The v2 `cold_start_fallback` was tuned on `realcartest_5k` and validated on `realcartest_3830_3920`; the original realcartest cross-segment low-budget failure could not be re-tested because that footage is no longer available. Source: `outputs/late_aqp_low_budget_fix_v1/README.md` "Caution".
- **Hybrid cold-start and v2 cold-start are failed routes on the original failure segments.** Both v2 (`outputs/late_aqp_v2_original_segment_verification/verdict_report.md`) and hybrid (`outputs/late_aqp_hybrid_coldstart_v1/verdict_report.md`) reported 0/3 segments with substantive improvement at both B=10 and B=20. The low-budget problem is **not solved by these cold-start tweaks**.

## Current Loop State

The current loop state covers the LATE-AQP frontier and the negative Phase 3 selector smoke. Inputs:

- `outputs/late_aqp_limited_oracle_frontier_v1/` (strict-replay oracle adapter, 12-question audit, cross-video extension in `late_aqp_cross_video_frontier_v1/`).
- `outputs/late_aqp_event_diverse_discovery_v1/` (D0/D1/D2/D3/D3-norepair, repair marginal value, 9-question audit).
- `outputs/late_aqp_d3_accounting_fix_v1/` (chunk-bandit `queried`-state bug fix and post-fix comparison).
- `outputs/late_aqp_core_halo_attribution_v1/` and `late_aqp_core_halo_frontier/` (Core/Halo attribution and frontier).
- `outputs/late_aqp_frozen_cross_segment_v1/` (frozen v1 config and cross-segment replay; the basis for the v1 to v2 fix loop).
- `outputs/late_aqp_algorithm_v3_oracle_relative/` (v3 audit-schedule and repair-utility designs, oracle-relative dense calibration plan).
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/` (the negative Phase 3 selector smoke).
- `outputs/cheap_signal_v2/` and `outputs/probe_set_v1/` (downstream inputs; the probe set remains **frozen / read-only** for evaluation only).

## Active Constraints

- **Do not run VLM, API, YOLO, or GPU inference without explicit authorization.** This applies to all future work, including any EC-AQP prototype.
- **Do not download datasets.**
- **Do not use `probe_set_v1` for tuning, threshold selection, selector choice, repair decisions, or candidate generation.** It is read-only evaluation.
- **Do not add formal guarantee fields or certificate logic.** This project targets empirical oracle-relative recall/precision, not statistical certificates.
- **Do not make CILS the default selector.** Default selector remains `score_topk` + temporal NMS + duration cap. CILS is ablation-only.
- **All oracle labels used in `outputs/late_aqp_*` are VLM-oracle-relative**, not human ground truth. This is true for both `center10_vlm_oracle_events.csv` (non-dev segments) and `reference_events.csv` (dev segment).
- **B6/B7/B6-core/B7-core are `posthoc_eval`** because their selection logic uses per-bin `event_id`. Only LATE-AQP-core (and D3-norepair-core on the D3 backbone) is `strict_replay`. When reporting LATE-AQP-core against B7-core, label which track the comparison lives in.
- **Outside-envelope audit samples that drive a repair decision cannot also be used to prove repair is effective.** Decision/evaluation samples must be different batches. This is enforced by the lineage schema (`outputs/late_aqp_frozen_cross_segment_v1/repair_trace_logging_spec.md`).

## Available Data

- **`probe_set_v1`** (`outputs/probe_set_v1/`): 25 probes with clips, center frames, and contact sheets. VLM-oracle labels at `probe_set_vlm_oracle_labels.csv` (25/25 parsed, 7 oracle-positive). **Read-only evaluation scope is 20/25** because cheap_signal_v2 feature coverage ends at local 1200s. **Frozen / not for tuning.**
- **`cheap_signal_v2`** (`outputs/cheap_signal_v2/`): track-interaction and inside/outside contrast feature tables. Coverage local `[0, 1200]` only; `feature_design_informed_by_6event_reference = yes`. Diagnostic-only.
- **`6_event_reference`**: 6 reference events. Used for `auc_best_direction` and `precision_at20_best_direction` design targets only; not a held-out eval set.
- **`expanded_reference`**: present but **empty**; do not cite results from it.
- **`center10_vlm_oracle_events*.csv`** (referenced by LATE-AQP): full-VLM per-anchor oracle reference for the main evaluation segments (`realcartest_0_1570`, `realcartest_2000_3200`, `realcartest_3200_3830`, `dataset3_0_1200`, `dataset3_1200_2400`, `dataset3_2400_3462`). Used for both `strict_replay` (LATE-AQP-core, D3-norepair-core) and `posthoc_eval` (B6/B7/B6-core/B7-core) tracks.
- **`realcartest_5k`** VLM-oracle labels newly written at `outputs/late_aqp_low_budget_fix_v1/new_labels/`: tuning-only labels for the v2 cold-start fix. Not used in main results.

## Known Time Axis

- `try_or_no/videos/realcartest.mp4` is **absent** in this workspace.
- LATE-AQP evaluation uses `center10_vlm_oracle_events.csv` (realcartest) and `dataset3_full_center10_parsed.csv` (dataset3), with per-segment local time windows defined in `outputs/late_aqp_limited_oracle_frontier_v1/full_vlm_reference_discovery_report.md`.
- `local_to_media_offset_seconds = 2000.0` for the probe_set_v1 fallback media (`data/realcam/long_video_data/long_video_dataset3.mp4`).
- Fallback media duration is `3462.930499s`.
- Current `probe_set_v1` covers local `[0.0, 1462.930499]`, not the full historical 66-minute realcartest video.
- Current cheap-signal feature tables cover local `[0, 1200]`.

## Last Review Outcome

- `outputs/late_aqp_limited_oracle_frontier_v1/FINAL_REPORT.md`: 12-question audit. LATE-AQP-core reaches 90/90 on 3/3 realcartest segments at B<=120. B7-core reaches 90/90 on 2/3. No method reaches 90/90 at <=30% budget ratio.
- `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md`: 9-question audit. D1/D2/D3/D3-norepair do not beat B7-core on B_90/90. Repair marginal value non-positive on chunk-bandit.
- `outputs/late_aqp_d3_accounting_fix_v1/FINAL_REPORT.md`: chunk-bandit `queried`-state bug fixed; D3-core vs D3-norepair remains non-positive. Pivot to D3-norepair recommended.
- `outputs/late_aqp_core_halo_attribution_v1/final_recommendation.md`: Core/Halo gain is generic, not LATE-specific. Hardest segment miss reasons: `upstream_discovery_miss` × 4. Mean guard overhead 29.6%.

## Agent Loop Progress (LATE-AQP focus)

- Round 1-9: completed under the previous `agent_loop_v1` cycle (Phase A/B artifacts, probe set v1, VLM-oracle labeling, first probe signal evaluation, Phase 3 selector smoke). See `outputs/agent_loop_v1/` and the previous state of this file.
- Round 10 (LATE-AQP core/halo): `outputs/late_aqp_core_halo_attribution_v1/`, `late_aqp_core_halo_frontier/` — Core/Halo is a generic post-processing gain; mean guard overhead 29.6%.
- Round 11 (frozen cross-segment): `outputs/late_aqp_frozen_cross_segment_v1/` — frozen v1 config passes 4 of 6 budgets on long-event recall; recommended replication on a second video.
- Round 12 (limited-oracle frontier): `outputs/late_aqp_limited_oracle_frontier_v1/` — strict limited-oracle replay; LATE-AQP-core reaches 90/90 on 3/3 segments; B7-core reaches 90/90 on 3/3 segments.
- Round 13 (event-diverse discovery): `outputs/late_aqp_event_diverse_discovery_v1/` — D1/D2/D3 redesign did not establish a discovery-side advantage over B7-core. D3-norepair-core is the strict-replay alternative.
- Round 14 (D3 accounting fix): `outputs/late_aqp_d3_accounting_fix_v1/` — `discovery_d3_chunk_bandit` `queried`-state bug fixed. Post-fix, repair is still not additive; pivot to D3-norepair.
- Round 15 (cross-video validation): `outputs/late_aqp_cross_video_frontier_v1/` — Core/Halo generic gain confirmed on dataset3; most low-budget failures are discovery misses. Recommended next step: continue upstream discovery redesign.
- Round 16 (low-budget diagnosis and v2 fix): `outputs/late_aqp_low_budget_discovery_diagnosis_v1/`, `late_aqp_low_budget_fix_v1/`, `late_aqp_v2_original_segment_verification/`, `late_aqp_hybrid_coldstart_v1/` — v2 cold-start fix is split-validated; cold-start and hybrid routes both `FAIL` on the original failure segments.
- Round 17 (algorithm v3 audit-schedule and repair-utility designs): `outputs/late_aqp_algorithm_v3_oracle_relative/` — modest improvements at B=20 with `V3_two_phase`; no utility dominates both recall and precision. Repair trace `source_action` lineage is **not** fully logged in the v3 replay.
- Round 18 (H7 calibration prep + long-event-only replay): `outputs/late_aqp_h7_long_event_v1/` — Ours-full improves event-level recall over B7 at most budgets for the long-event subset. H7 annotation package is **pending human annotation**.
- Round 19 (state sync): `outputs/state_sync_late_aqp_v1/` — this document and the accompanying root-level state files were resynchronized to reflect the LATE-AQP frontier and the Phase 3 selector smoke negative result.

## Current Blocker

There is no current blocker for the next no-new-VLM step.

**Recommended next direction: EC-AQP (Event-Coverage AQP) planning + residual missing-mass estimation.** T010 in `TASK_QUEUE.yaml`. The premise: current methods are strong once the event is in the candidate set; the open gap is **upstream discovery miss** under low budget. EC-AQP reframes the objective from per-interval precision/recall to **event-coverage mass over the reference event set** and adds a residual missing-mass estimator. Design only; no VLM, YOLO, or GPU.

Other design-only next steps considered but de-prioritized:
- Another discovery policy sweep along the D1/D2/D3 axes (D1/D2/D3 already failed to beat B7-core on B_90/90; the bottleneck is not the discovery prior but the small-sample cold start and the diversity of long events).
- Per-interval adaptive guard cap (guard overhead is 29.6% mean, 41.4% at B<=20; but reducing it directly costs boundary precision and is not clearly worth it given the discovery-miss dominant failure mode).
- Mechanism-comparison paper pivot (deferred: the empirical case for stopping the performance route is no longer clean after the D3 accounting fix; continuing to look for an event-coverage route is the more honest next step).
