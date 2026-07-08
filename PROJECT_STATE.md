# SQ-CRAQ Project State

Last updated: 2026-07-07

## Current Stage

**Limited-oracle temporal event retrieval / LATE-AQP frontier.**
We have completed the first executable LATE-AQP pipeline (audit + discovery + repair + boundary guard + Core/Halo release) and validated it under strict limited-oracle replay across six segments of two videos (`realcartest`, `dataset3`). The pipeline reaches 90/90 event precision/recall on every qualified segment at the practical budget cap (B<=120), and the strongest current empirical baselines are **B7-core** and **D3-norepair-core** (chunk-bandit discovery, no repair, Core/Halo release). Core/Halo has been shown to be a **generic post-processing gain** that lifts B6/B7 to the same 90/90 frontier as LATE-AQP-core; the LATE-specific advantage over these release-augmented baselines is **not established** for performance alone.

**Active direction pivot (2026-07-07): Event-Coverage Policy (ECP).** The
next mainline is no longer "improve the proxy / discovery heuristic". The
reframed bottleneck is the absence of an **event-level budgeted decision
policy** under a weak proxy, an expensive VLM oracle, and unknown event
boundaries (see `outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`). EC-AQP's
event-coverage-mass objective is absorbed as the reward term inside ECP. ECP
unifies DISCOVER + ROBUST_PROBE (StagRepMix) + BRIDGE (AnchorBridge) + CERTIFY +
ZERO_PROXY as event-level arms of a contextual bandit; HTS-EC / EventLift-DC are
candidate executors. Default selector and Core/Halo release are unchanged.
Validation sequence: T025 (AnchorBridge shadow) -> T026 (action-utility
labeling) -> T027 (hand-designed bandit) -> offline learned policy.

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
- **The dominant low-budget failure is upstream discovery miss — but the deeper gap is event formation, not proxy accuracy.** Limited-oracle frontier failure taxonomy: 6 discovery_miss vs 6 release_over_conservative vs 3 LATE-specific. Source: `outputs/late_aqp_limited_oracle_frontier_v1/failure_taxonomy.csv`. Core/Halo is already effective when discovery finds the events. The 2026-07-07 reframing (`outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md`) argues the open lever is an **event-level budgeted decision policy** (where to look / verify / expand / stop / abstain) above the discovery executor, not a more accurate proxy. The proxy-zero regime (`dataset3_0_1200`: 7/7 true positives at proxy=0.0 among 76 zero-proxy bins) is an information bottleneck needing explicit proxy-free exploration.
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
- Round 20 (ECP reframing): `outputs/ecp_event_coverage_policy_v1/ECP_DESIGN.md` — mainline redefined from EC-AQP to **Event-Coverage Policy (ECP)**: event-level contextual bandit above the discovery executor, arms = discover/bridge/certify/zero-proxy/stop, reward = marginal event-recall/precision/IoU. Validation plan T025->T026->T027.
- Round 21 (ECP Steps 1-3 experiments): `outputs/ecp_event_coverage_policy_v1/{t025_anchorbridge_shadow*, t026_action_utility.csv, t027_ecp_bandit_*, ECP_STEPS1_3_SYNTHESIS.md}`. T025: positives within an event are already contiguous (gap-bridging near-empty); real formation gap is temporal granularity (sub-1s events in 10s bins) + proxy-zero discovery. T026: BRIDGE most efficient arm (0.474 pos rate) but under-used by hand weights. T027: hand-designed ECP bandit runs strict-replay, matches/beats HTS-EC-safe on realcartest, still weak on dataset3 (proxy-zero). T028 (reweight + learned policy) pending.
- Round 22 (ECP Step 4 experiments): `outputs/ecp_event_coverage_policy_v1/{t028a_ecp_bandit_*, t028b_ecp_learned_*, ECP_STEP4_SYNTHESIS.md}`. T028a: reweighted v2 fixes BRIDGE under-use (633 calls @0.441 pos; ZERO_PROXY 48 @0.125) but is NOT clearly better than v1 (lower on 2 realcartest cells). T028b: offline logistic policy trained on T026/v2 logs == v2 on every cell — offline learning from logged choices only re-learns the logger (standard offline-bandit limitation). Claim "ECP improves low-budget coverage over B7-core" STILL NOT supported. Next: T028c (event-utility reward) / T028d (IPS/DR debiasing).
- Round 23 (ECP Step 4c experiments): `outputs/ecp_event_coverage_policy_v1/{ecp_candidate_utility_by_step.csv, ecp_oracle_ceiling_frontier.csv, t028c0_ceiling_report.md, t028c1_event_utility_policy_*, ECP_STEP4C_SYNTHESIS.md}`. T028c-0 oracle ceiling: learnable event-level signal EXISTS on proxy-informative realcartest (+0.10..+0.14 over v2 on cells v2 regressed on) but NOT on proxy-zero dataset3_0_1200/1200_2400 (candidate generator cannot propose zero-proxy positives -> ceiling≈0). T028c-1 event-utility ranker (GradientBoosting on u(arm|state,arm), trained on candidate-level utilities NOT logger-confined) is strict-replay and RECOVERS the ceiling on collapsed cells: realcartest_3200_3830 @0.30 c1 0.286=ceiling beats v2 0.143; realcartest_0_1570 @0.30 c1 0.250 vs v2 0.200; dataset3_2400_3462 c1 0.111>v2 0.000. First ECP variant to beat v2 on realcartest without precision loss. T028d deferred (needs stochastic logger); T028e (proxy-free candidate generator) is the real next lever for dataset3.
- Round 24 (ECP Step 4c-2 LOSO): `outputs/ecp_event_coverage_policy_v1/{t028c2_loso_*, t028c2_loso_synthesis.md}`. T028c-2 leave-one-segment-out (6-fold) validation. c1 generalizes on realcartest held-out: 0 regressions, 4/9 cells c1>v2 (up to +0.143), 3/9 ties, 2/9 ceiling-reached. Action shift: c1 uses more DISCOVER+CERTIFY, less BRIDGE. dataset3 held-out: c1<=v2 on all 9 cells (candidate-generator bottleneck, ceiling also ~0). Verdict: c1 generalizes on proxy-informative segments; does NOT solve proxy-zero. Next: T028e (proxy-free candidate generator).
- Round 25 (ECP Step 4e proxy-free candidates): `outputs/ecp_event_coverage_policy_v1/{t028e0_ceiling_*, t028e1_loso_*, t028e_synthesis.md}`. T028e-0 ceiling audit: added 5 proxy-free arms (SPACE_FILLING, LARGEST_GAP, VDC, MIDBAND, LOCAL_GAP_FLANK). dataset3_1200_2400 ceiling lifts +0.083 (from 0.000 to 0.083). dataset3_0_1200 ceiling stays 0 (sparse positives). T028e-1 strict-replay LOSO: c2 matches c1 on realcartest (0 regressions) AND beats v2 on 2/9 dataset3 cells. Most importantly: c2=0.167 on dataset3_0_1200 @0.20/0.30 vs v2=0.000 (ceiling was 0) — proxy-free VDC arm resolves the candidate-generator bottleneck on that segment. Per-seed deterministic. Next: T028e-2 (expand VDC/diversity on remaining dataset3 segments) or T028d (IPS/DR with stochastic logger).

## Current Blocker

There is no current blocker for the next no-new-VLM step.

**Recommended next direction: ECP (Event-Coverage Policy).** T010 in `TASK_QUEUE.yaml`
is now the ECP mainline (replaces the narrower EC-AQP framing). The premise:
current methods are strong once an event is in the candidate set, but the open
gap is **event-level decision-making under weak proxy / expensive oracle /
unknown boundaries** — specifically the missing `positive anchor -> event
hypothesis -> interval confirmation` layer and the lack of a unified
event-utility budget loop. ECP reframes the objective as an event-level
contextual bandit whose reward is marginal event-recall / precision / IoU.

**ECP Steps 1-4c-2 are now run (Rounds 21-24):** T025/T026/T027 established the
structure; T028a/T028b showed fixed weights and logged-choice learning do NOT
beat v2. **T028c broke through**: T028c-0 ceiling proved learnable signal on
proxy-informative realcartest but not proxy-zero dataset3 (candidate-generator
bottleneck); T028c-1 ranker beats v2 on realcartest. **T028c-2 LOSO validated
generalization**: c1 generalizes on realcartest held-out (0 regressions, 4/9
improvements up to +0.143) but NOT on dataset3 (candidate-generator bottleneck).
The claim "ECP-utility-c1 improves low-budget event coverage" is now
**supported on proxy-informative realcartest, still not on proxy-zero dataset3**
— report per-segment, do not over-claim. T028d (IPS/DR) is deferred until a
stochastic logger exists; T028e (proxy-free candidate generator) is the real
next lever for dataset3.

Other design-only next steps considered but de-prioritized: `outputs/ecp_event_coverage_policy_v1/{ecp_candidate_utility_by_step.csv, ecp_oracle_ceiling_frontier.csv, t028c0_ceiling_report.md, t028c1_event_utility_policy_*, ECP_STEP4C_SYNTHESIS.md}`. T028c-0 oracle ceiling: learnable event-level signal EXISTS on proxy-informative realcartest (+0.10..+0.14 over v2 on cells v2 regressed on) but NOT on proxy-zero dataset3_0_1200/1200_2400 (candidate generator cannot propose zero-proxy positives -> ceiling≈0). T028c-1 event-utility ranker (GradientBoosting on u(arm|state,arm), trained on candidate-level utilities NOT logger-confined) is strict-replay and RECOVERS the ceiling on collapsed cells: realcartest_3200_3830 @0.30 c1 0.286=ceiling beats v2 0.143; realcartest_0_1570 @0.30 c1 0.250 vs v2 0.200; dataset3_2400_3462 c1 0.111>v2 0.000. First ECP variant to beat v2 on realcartest without precision loss. T028d deferred (needs stochastic logger); T028e (proxy-free candidate generator) is the real next lever for dataset3.

## Current Blocker

There is no current blocker for the next no-new-VLM step.

**Recommended next direction: ECP (Event-Coverage Policy).** T010 in `TASK_QUEUE.yaml`
is now the ECP mainline (replaces the narrower EC-AQP framing). The premise:
current methods are strong once an event is in the candidate set, but the open
gap is **event-level decision-making under weak proxy / expensive oracle /
unknown boundaries** — specifically the missing `positive anchor -> event
hypothesis -> interval confirmation` layer and the lack of a unified
event-utility budget loop. ECP reframes the objective as an event-level
contextual bandit whose reward is marginal event-recall / precision / IoU.

**ECP Steps 1-4c are now run (Rounds 21-23):** T025/T026/T027 established the
structure (event-level bandit above the executor, viable strict-replay, matches/
beats HTS-EC-safe on proxy-informative realcartest). T028a/T028b showed fixed
weights and offline learning from logged choices do NOT beat v2. **T028c broke
through**: T028c-0 ceiling proved learnable event-level signal exists on
proxy-informative realcartest but not on proxy-zero dataset3 (candidate-generator
bottleneck); T028c-1 event-utility ranker (trained on candidate-level utilities,
not logger-confined) is strict-replay and recovers the ceiling on the cells v2
regressed on — **the first ECP variant to beat v2 on realcartest without precision
loss**. Proxy-zero dataset3 remains blocked at the candidate-generator level
(not the policy); T028d (IPS/DR) is deferred until a stochastic logger exists;
T028e (proxy-free candidate generator) is the real next lever. The claim "ECP
improves low-budget event coverage over B7-core" is now **partially supported on
proxy-informative realcartest, still not supported on proxy-zero dataset3** —
report per-segment, do not over-claim.

Other design-only next steps considered but de-prioritized:
- Another discovery policy sweep along the D1/D2/D3 axes (D1/D2/D3 already failed to beat B7-core on B_90/90; the bottleneck is not the discovery prior but the small-sample cold start and the diversity of long events).
- Per-interval adaptive guard cap (guard overhead is 29.6% mean, 41.4% at B<=20; but reducing it directly costs boundary precision and is not clearly worth it given the discovery-miss dominant failure mode).
- Mechanism-comparison paper pivot (deferred: the empirical case for stopping the performance route is no longer clean after the D3 accounting fix; continuing to look for an event-coverage route is the more honest next step).
