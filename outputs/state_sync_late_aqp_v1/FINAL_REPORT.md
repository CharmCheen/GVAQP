# FINAL REPORT — State Sync to LATE-AQP Frontier (Round 19)

## 1. Scope and constraints

- **No GPU / VLM / API was used.** All changes are documentation / metadata only.
- **No experiments were run.**
- **No experimental outputs in `outputs/late_aqp_*/` were modified.**
- **No files were deleted.** A new directory `outputs/state_sync_late_aqp_v1/` was created.
- **No git push was performed.**
- **Negative results are surfaced, not hidden.** The Phase 3 selector smoke negative and the LATE-AQP non-improvement vs B7-core are explicit in the new state files.

## 2. Which files were updated

Root-level state files (modified):

- `PROJECT_STATE.md` — replaced the Phase A/B / Phase 3 framing with the LATE-AQP frontier description. Added the two-track situation, the active conclusions (Core/Halo is generic; repair is neutral post-fix; no LATE variant beats B7-core; dominant low-budget failure is upstream discovery miss), the round-10-18 LATE-AQP agent-loop progress, and the EC-AQP next direction.
- `HANDOFF.md` — added a "mainline" preamble that names the default selector / default release / strongest baseline / strict-replay alternative, the latest important `outputs/late_aqp_*/FINAL_REPORT.md`s to read first, the do-not-repeat failed routes, the completed agent-loop items (T001-T019), and the ready-for-no-compute next step (T010).
- `TASK_QUEUE.yaml` — closed T001-T006 / T009 / T011-T018; set T010 to `active` and `highest` priority; added T019 (this round), T020 (EC-AQP design), T021 (large-artifact externalization decision), T022 (EC-AQP offline prototype). Downgraded T007 / T008 to `low` priority and explicitly marked them as **not on the mainline**.
- `CLAIMS_LEDGER.md` — restructured into "Can claim (with source)", "Cannot claim (explicit disallowed wording)", and "Pending validation". Each can-claim entry lists the source file, the track (`strict_replay` / `posthoc_eval`), and the caveats. Each cannot-claim entry cites the source that contradicts the disallowed wording.
- `FAILURES.md` — re-listed failed and neutral routes: Phase 3 fixed cheap-signal selector, v2 cold_start_fallback on original failure segments, hybrid_coldstart, D1/D2/D3 vs B7-core on B_90/90, Core/Halo as LATE-specific, pre-fix repair net-negative (contaminated), <=30% budget 90/90 (no method), label-isolation risk, V3 audit/repair designs (modest only). The active warnings block was preserved.
- `EXPERIMENT_REGISTRY.csv` — added 13 `late_aqp_*` entries (algorithm_v3_oracle_relative, core_halo_attribution_v1, core_halo_frontier, cross_video_frontier_v1, d3_accounting_fix_v1, event_diverse_discovery_v1, frozen_cross_segment_v1, h7_long_event_v1, hybrid_coldstart_v1, limited_oracle_frontier_v1, low_budget_discovery_diagnosis_v1, low_budget_fix_v1, repair_negative_diagnosis_v1, v2_original_segment_verification) plus the `state_sync_late_aqp_v1` self-entry. Updated the `phase3_selector_smoke_v1` decision to `COMPLETED_NEGATIVE_DIAGNOSTIC` to match the new framing.
- `AGENTS.md` — added a "Current mainline" section that names the LATE-AQP frontier, the default selector / release / baseline / strict-replay alternative, the EC-AQP next priority. Added explicit "never" rules against claiming LATE-AQP beats B7-core, claiming Core/Halo is LATE-specific, and deriving a "repair is net-negative" conclusion from pre-fix data. Added explicit disallowed wording for the common misleading phrasings (true recall, formal guarantee, etc.). Added the large-artifact warning block.

New file:

- `outputs/state_sync_late_aqp_v1/large_artifact_manifest.md` — exhaustive list of files > 5 MB tracked by git, files > 50 MB regardless of tracking, and ignored model / dataset / video binaries. Includes tracked/ignored status, source/context, and a recommended action for each tracked file.
- `outputs/state_sync_late_aqp_v1/FINAL_REPORT.md` — this file.

Total file changes: 7 modified root files, 2 new files. No files deleted.

## 3. What current research state is now reflected

The root state files now describe the project at the **LATE-AQP frontier**, not the older Phase A/B / Phase 3 framing. Specifically:

- **Current phase** = "Limited-oracle temporal event retrieval / LATE-AQP frontier." The 13 LATE-AQP experiments are listed in `EXPERIMENT_REGISTRY.csv` and form the mainline.
- **Two-track situation** = (1) LATE-AQP frontier on `center10_vlm_oracle_events.csv` / `reference_events.csv`; (2) Phase 3 selector smoke on the smaller `probe_set_v1` scope. They are explicitly distinguished and not directly comparable.
- **Phase 3 selector smoke** is now `COMPLETED_NEGATIVE_DIAGNOSTIC` and is the empirical motivation for T010 (EC-AQP redesign).
- **Core/Halo release** is now described as a **generic post-processing gain** with a quantified guard overhead (29.6% mean, 41.4% at B<=20). It is the default release module, not a LATE-specific advantage.
- **Strongest current empirical baseline** (posthoc_eval) = **B7-core**. Strongest strict-replay alternative = **D3-norepair-core**. The previous "D3-core + repair" formulation is replaced by "D3-norepair-core" because the post-fix D3-core is **not** consistently better.
- **Repair marginal value is neutral after the D3 accounting fix** (95.4% duplicate-call reduction, but no consistent recall / B_90/90 gain over D3-norepair-core).
- **Next direction** = **EC-AQP** (event-coverage mass + residual missing-mass estimator) on the existing `center10_vlm_oracle_events.csv` / `reference_events.csv`. No new VLM, YOLO, or GPU.
- **All oracle labels remain VLM-oracle-relative**, not human ground truth. Every recall/precision number in any future write-up must cite the data source and the track.

## 4. Which stale claims were removed

- Removed: "Project current stage is Phase A/B artifact stabilization + Phase 3 minimal selector smoke" (the previous `PROJECT_STATE.md` Current Stage section).
- Removed: "Phase 3 selector smoke is `diagnostic_design_target_smoke`, not validation" as a soft qualifier. The new wording is `COMPLETED_NEGATIVE_DIAGNOSTIC`, which is the operational status.
- Removed: "Consider redesigning the AQP selector/return-set objective before making stronger AQP claims" as a *future* suggestion. The redesign is now the active highest-priority task (T010) and is framed as EC-AQP, not as "another D1/D2/D3 sweep".
- Removed: "no current blocker" in the spirit of "no urgency"; the new HANDOFF explicitly states the next no-compute step (T010) and lists the do-not-repeat failed routes.
- Removed: implicit "any LATE variant might beat B7-core" framing. The new CLAIMS_LEDGER makes "no LATE variant beats B7-core on B_90/90" an explicit disallowed claim, sourced to `outputs/late_aqp_event_diverse_discovery_v1/FINAL_REPORT.md` Q4.
- Removed: implicit "Core/Halo is LATE-AQP-specific" framing. The new CLAIMS_LEDGER makes this an explicit disallowed claim.
- Removed: implicit "repair is net-negative" framing. The new CLAIMS_LEDGER makes deriving this conclusion from pre-fix data an explicit disallowed claim, and the post-fix statement is "neutral after the fix".
- Removed: implicit "we should expand probe_set_v1" framing. T007/T008 are now `low` priority and explicitly **not on the mainline**.
- Removed: implicit "v2 cold_start_fallback fixes the low-budget problem" framing. The new FAILURES / HANDOFF make it clear that the v2 fix is **split-validated, not re-validated on the original failure segments**.
- Removed: implicit "H7 annotation is the next H-thing to do" framing. H7 is now described as the **next annotation opportunity, not the LATE-AQP performance conclusion**, and is still blocked on explicit authorization.

## 5. Which tasks are active

- **T010 — AQP selector/return-set redesign toward EC-AQP** (status: `active`, priority: `highest`). Pure design, no VLM, no YOLO, no GPU. Lists the inputs to read first and the success criteria.
- **T019 — Agent state sync to LATE-AQP frontier** (status: `complete`). This round's deliverable.
- **T020 — EC-AQP design (objective, residual missing-mass estimator, falsifier)** (status: `pending`, priority: `high`). Successor to T010.
- **T021 — Decide on externalization of > 100 MB CSV artifacts** (status: `pending`, priority: `medium`). See the manifest for the proposed actions; user decision required.
- **T022 — EC-AQP offline prototype on existing center10 labels** (status: `pending`, priority: `medium`). Blocked on T020.

Other tasks (T001-T009, T011-T018) are `complete`; T007 / T008 are `blocked` / `pending` and explicitly de-prioritized.

## 6. Which large artifacts need a user decision

T021 in `TASK_QUEUE.yaml`. Per `large_artifact_manifest.md`:

| Path | Size | Tracked? | Recommendation |
|---|---:|---|---|
| `src/garc_eval/outputs/cils_empty_return_root_cause_audit_v1/cils_rejection_trace.csv` | 638 MB | yes | Externalize (or gitignore). CILS is ablation-only; the audit's report MD already contains the summary. |
| `src/garc_eval/outputs/cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv` | 481 MB | yes | Externalize (or gitignore). Same rationale; the smoke's `calibration_repair_report.md` contains the summary. |
| `src/garc_eval/outputs/cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv` | 195 MB | yes | Externalize (or gitignore). Same rationale; the replay's `repair_vs_clean_v2_summary.md` contains the summary. |
| `src/garc_eval/outputs/synthetic_cheap_signal_downstream_validation_v1/synthetic_signal_candidates.csv` | 120 MB | yes | Externalize (or gitignore). The validation's `metrics_summary.csv` and `FINAL_REPORT.md` contain the summary. |
| `try_or_no/outputs/real_kinematic_mvp/kinematic_query_table.csv` | 99 MB | yes | Externalize (or gitignore, try_or_no/ scope). Legacy track; not on the LATE-AQP mainline. |

None of these have been moved or deleted. The manifest also includes a per-file source / context note. The 12 ignored artifacts > 50 MB (datasets, models, MP4 clips, etc.) are listed for completeness and are not in scope of the externalization decision.

## 7. Verification (what an agent reading the new state files should conclude)

Reading `PROJECT_STATE.md` first, then `CLAIMS_LEDGER.md`, then `HANDOFF.md`, an agent should conclude:

1. The current mainline is LATE-AQP. The Phase 3 selector smoke is a completed negative diagnostic, not an active experiment.
2. The default selector is `score_topk` + temporal NMS + duration cap. The default release is Core/Halo. The strongest empirical baseline to beat is **B7-core**; the strongest strict-replay alternative to use is **D3-norepair-core**.
3. LATE-AQP does **not** beat B7-core on B_90/90. Do not claim that it does.
4. Core/Halo is a generic post-processing gain. Do not claim it is LATE-specific.
5. Repair is **neutral after the D3 accounting fix**. Do not derive a "repair is net-negative" claim from the pre-fix data.
6. The strongest negative result to act on is the **Phase 3 selector smoke** (cheap-signal selectors underperform uniform random at B=40). T010 (EC-AQP) is the active highest-priority next step.
7. probe_set_v1 is **frozen / read-only** for evaluation only. T007 / T008 are blocked and **not on the mainline**. Do not promote them above T010.
8. All oracle labels in `outputs/late_aqp_*` are VLM-oracle-relative. Cite the data source and the track on every recall/precision number.
9. No VLM, YOLO, GPU, or API is allowed without explicit authorization. H7 human annotation is the next annotation milestone, blocked on authorization.
10. The five > 100 MB CSVs listed in `large_artifact_manifest.md` are tracked as plain blobs. A user decision is required to externalize them.

## 8. Do-not-repeat summary

The new `FAILURES.md` lists these in full. Quick reminder:

- Do not run another D1/D2/D3 sweep along the same axes (D1/D2/D3/D3-norepair did not beat B7-core on B_90/90).
- Do not promote v2 cold_start_fallback as a low-budget fix on the original failure segments (the original footage is no longer available; the v2 fix is split-validated only).
- Do not promote hybrid_coldstart as a low-budget fix (0/3 segments with substantive improvement at both B=10 and B=20).
- Do not derive a "repair is net-negative" conclusion from pre-fix D3 data (the chunk-bandit `queried`-state bug was fixed in `late_aqp_d3_accounting_fix_v1/`).
- Do not claim Core/Halo is a LATE-AQP-specific advantage (B6-core and B7-core reach 90/90 on the same segments).
- Do not claim CILS is the default selector.
- Do not claim "any method reaches 90/90 at <=30% budget ratio" on realcartest or dataset3.
- Do not claim "true recall" / "ground truth recall" for any metric in this repo.
- Do not run VLM, YOLO, GPU, or API inference without explicit authorization.

## 9. What was NOT done in this round

- No experiments were run.
- No experimental outputs were modified.
- No files were deleted.
- No git push was performed.
- No new claims were added; this round is documentation / metadata only.
- The `cheap_signal_v2` and `probe_set_v1` CSVs were not re-evaluated; their state files were not touched.
- The `try_or_no/` legacy code was not modified.
- The model / dataset / video situation was not modified.
