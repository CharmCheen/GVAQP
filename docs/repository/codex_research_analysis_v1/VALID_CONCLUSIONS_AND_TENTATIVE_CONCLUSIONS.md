# Valid Conclusions and Tentative Conclusions

## Status Preservation Note

This analysis preserves the status labels from `repo_audit_for_codex_v1/DECISION_LOG.md`. In particular, V13.7 performance claims remain `superseded`; Micro-CASQ candidate feasibility remains `partially_valid`; the nuScenes event-AQP feasibility item remains `unknown` and is not used as evidence; and the audit records no remaining `needs_code_review` item after the V13.10 mismatch and adaptive-search verification addenda.

## A. Safe to Cite Now

### Claim: The V13.8 full center10 oracle reference is ready.

- Supporting evidence: `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/reports/FINAL_REPORT.md`; `repo_audit_for_codex_v1/KEY_RESULTS_TABLE.csv`.
- Scope: Single video, `realcartest.mp4`; Qwen3-VL-32B VLM-oracle-relative labels.
- Caveat: Not human ground truth and not a multi-video benchmark.
- Supports AQP contribution: Yes, as evaluation infrastructure. It provides the fixed oracle reference needed for budgeted selection experiments.

### Claim: The current reference has 399 anchors, 94 positive anchors, 305 negatives, 0 abstain, and 51 stitched events.

- Supporting evidence: V13.8 final report and V13.8 oracle/event tables listed in `repo_audit_for_codex_v1/ARTIFACT_INVENTORY.md`.
- Scope: VLM-oracle-relative, single-video full center10 scan.
- Caveat: The 23.6% positive-anchor rate may not generalize.
- Supports AQP contribution: Yes, as a concrete benchmark instance, but not as a guarantee result.

### Claim: `center_10s` is the current best coarse construction choice for this pipeline.

- Supporting evidence: `test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/reports/FINAL_REPORT.md`.
- Scope: 52-clip sensitivity sample on one video, VLM-oracle-relative labels.
- Caveat: It should be described as validated for `realcartest.mp4`, not a universal clip-granularity result.
- Supports AQP contribution: Partially. It is benchmark construction and oracle-cost reduction, not a standalone AQP method.

### Claim: Cheap static proxies are weak on the unbiased V13.8 full reference.

- Supporting evidence: `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/reports/FINAL_REPORT.md`; `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`.
- Scope: Static methods using current YOLO/motion/geometry proxy features over V13.8.
- Caveat: This is a negative result for tested proxies, not proof that no proxy can work.
- Supports AQP contribution: Yes as motivation and problem diagnosis; no as a positive method contribution.

### Claim: V13.10 OracleBest direct event-discovery upper bound is B=5 -> 0.098, B=10 -> 0.196, B=20 -> 0.392, B=40 -> 0.784, B=80 -> 1.000.

- Supporting evidence: `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`; `test_vlm/outputs/v13_10/tables/oracle_upper_bound_v13_10.csv`.
- Scope: Direct event-discovery recall over 51 stitched VLM-defined events.
- Caveat: This is an oracle upper bound, not an achievable method result.
- Supports AQP contribution: Yes as an evaluation diagnostic and efficiency denominator.

### Claim: On this dataset, V13.9 temporal-overlap event recall and V13.10 direct event-discovery recall agree for deterministic methods.

- Supporting evidence: `test_vlm/outputs/v13_10/reports/V13_10_MISMATCH_ROOT_CAUSE.md`.
- Scope: Current center10 grid and V13.8 stitched events.
- Caveat: The equivalence depends on this anchor grid and event geometry. It should not be assumed for other datasets without checking.
- Supports AQP contribution: Yes, by cleaning up metric interpretation.

## B. Safe to Cite Only With Caveats

### Claim: V13.7 showed proxy methods can beat random on a center10 labeled subset.

- Supporting evidence: `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/reports/FINAL_REPORT.md`.
- Scope: 52 labeled clips from V13.6, pilot-derived subset.
- Caveat: The subset was biased, including high-YOLO samples. Do not cite V13.7 recall numbers as current method performance; cite only as the rationale that led to V13.8.
- Supports AQP contribution: Weakly, as historical exploration only.

### Claim: Adaptive search was evaluated and did not improve over static methods.

- Supporting evidence: `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`.
- Scope: Six adaptive variants, three base scores, five budgets, current proxies.
- Caveat: It rules out these adaptive mechanisms under the current weak proxy scores. It does not rule out adaptive query execution with a better state update or stronger semantic scorer.
- Supports AQP contribution: As a negative result and cautionary baseline.

### Claim: Nexar-derived labels are unreliable for `O_enter_ego_path_v0`.

- Supporting evidence: `test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/reports/EXTERNAL_LABEL_MAPPING.md`; `test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/reports/VLM_MICRO_AUDIT_REPORT.md`.
- Scope: Nexar-200 derived-boundary pipeline.
- Caveat: This only says the current external-label mapping is unreliable for this predicate, not that Nexar videos are useless if re-labeled under the right oracle.
- Supports AQP contribution: Indirectly, by ruling out a weak benchmark source.

### Claim: Micro-CASQ candidate feasibility passed but certificate evidence is underpowered.

- Supporting evidence: `test_vlm/outputs/v12_1_completion_v1/reports/V12_1_COMPLETION_FINAL_REPORT.md`; `test_vlm/outputs/clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md`.
- Scope: Sampled Micro-CASQ benchmark and Phase 0 pseudo-event simulation.
- Caveat: Not full-video retrieval and not current V13 evidence.
- Supports AQP contribution: Partially; it supports infrastructure history, not current proof.

## C. Superseded or Should Not Be Cited

### Claim: V13.7 labeled-subset B=20 recall of 0.448 demonstrates current proxy success.

- Supporting evidence: V13.7 final report only.
- Scope: Biased labeled subset.
- Caveat: Superseded by V13.9/V13.10 full-reference results. It should not be cited as current evidence.
- Supports AQP contribution: No.

### Claim: V13.5's 66% abstain rate describes the current oracle prompt.

- Supporting evidence: V13.5 pilot labels.
- Scope: Old prompt only.
- Caveat: Superseded by V13.6 prompt repair and V13.8 0% abstain full scan.
- Supports AQP contribution: No, except as prompt-debugging history.

### Claim: V13.9 IoU event recall fields prove no method finds events.

- Supporting evidence: V13.9 CSV IoU columns.
- Scope: IoU fields `event_recall_iou_0p3` and `event_recall_iou_0p5`.
- Caveat: These fields are unsuitable for 10s anchor windows and are always 0.0 in the audit. Use `event_recall_overlap` and the V13.10 direct event-discovery comparison instead.
- Supports AQP contribution: No.

### Claim: Nexar-200 derived boundaries are oracle-relative labels for `O_enter_ego_path_v0`.

- Supporting evidence: External label mapping and VLM micro-audit contradict this claim.
- Scope: Nexar candidate feasibility.
- Caveat: Must be reported only as Nexar-derived-boundary-relative unless re-labeled.
- Supports AQP contribution: No.

### Claim: Any current recall number is human-truth recall.

- Supporting evidence: None.
- Scope: All audited V13 and Micro-CASQ labels.
- Caveat: No human-adjudicated benchmark exists.
- Supports AQP contribution: No; overclaiming would weaken the work.

## D. Still Needs Code Review or Metric Reconciliation

### Claim: V13.10 adaptive search conclusion is valid after code-review concerns.

- Supporting evidence: `repo_audit_for_codex_v1/DECISION_LOG.md` marks no current `needs_code_review` items; V13.10 report includes verification addenda; mismatch report identifies resolved comparison issues.
- Scope: Current V13.10 scripts and tables.
- Caveat: The audit says the code-review issue is resolved, but the conclusion remains tied to the tested mechanisms and proxies.
- Supports AQP contribution: Negative evidence only.

### Claim: Temporal-overlap coverage recall and direct event-discovery recall are identical in general.

- Supporting evidence: V13.10 mismatch root-cause report supports equivalence only on this dataset.
- Scope: Current center10 grid and V13.8 stitched events.
- Caveat: For future videos or different anchor construction, keep reporting both definitions until reconciliation is repeated.
- Supports AQP contribution: Yes as evaluation hygiene, but not as a universal theorem.

### Claim: The statistical certificate layer is ready on V13.8.

- Supporting evidence: Not currently available.
- Scope: V13.8 full oracle.
- Caveat: Certificate simulation has not been run on the valid V13.8 oracle, and prior certificate work was underpowered.
- Supports AQP contribution: This is the main missing piece for a strong AQP claim.

### Claim: Representation or 8B cascade will solve proxy quality.

- Supporting evidence: None in current results; these are recommendations.
- Scope: Future work.
- Caveat: Must be tested without using V13.8 labels for training/ranking leakage.
- Supports AQP contribution: Potentially, if framed as oracle-allocation evidence rather than perception-method invention.
