# Current Status Assessment

## 1. Current Research Problem

The current CASQ / G-ClipAQP problem is a database/AQP-style approximate semantic event selection problem over long driving videos. Under a fixed expensive oracle contract, the system should use a limited oracle budget to return event-containing variable-length clips and eventually support conservative clip-level recall certification.

The strongest current framing from `repo_audit_for_codex_v1/EVIDENCE_PACK.md` and `CASQ_CODEX_BRIEF_V12_1.md` is not "build the best driving-event detector." It is: given any candidate generator or proxy, an expensive oracle, a budget, target recall, and failure probability, can the system produce useful event retrieval and a conservative oracle-relative recall statement? The certificate layer has not yet been validated on the current V13 full oracle.

## 2. Current Query Predicate

The active predicate is `O_enter_ego_path_v0`:

```text
A road participant enters or clearly intrudes into the ego vehicle's future driving path, e.g. vehicle cut-in, pedestrian crossing, cyclist entering path.
```

The repository reports phrase this as an object starting outside or near the ego future path and then entering or overlapping it, creating potential spatial conflict requiring ego attention. All current labels for this predicate are VLM-oracle-relative, primarily Qwen3-VL-32B, not human ground truth.

## 3. What Has Been Experimentally Validated

- V13.6 validated `center_10s` as the best current coarse oracle construction for `realcartest.mp4`: 399 estimated full-video calls instead of 798 fixed 5s calls, 56% positive rate on the 52-clip sensitivity sample versus 44% for fixed 5s, 0% abstain, 100% complete event visibility, and 0% truncation.
- V13.8 constructed the current strongest reference: 399/399 center10 anchors processed, 94 positive anchors, 305 negative anchors, 0 abstain, and 51 stitched VLM-defined events.
- V13.9 evaluated 19 static selection methods over the V13.8 full reference. On the primary full-reference event-recall-overlap metric, cheap proxy methods were weak: at B=20, uniform selection was best with event recall 0.137 and the proxy delta versus random was only +0.059.
- V13.10 established the direct event-discovery OracleBest upper bound: B=5 -> 0.098, B=10 -> 0.196, B=20 -> 0.392, B=40 -> 0.784, B=80 -> 1.000. Static methods were far below this bound at B=20 and B=40.
- V13.10 also evaluated simple adaptive priority boost and bidirectional expansion. Under the current proxy scores, adaptive methods did not beat the best static method at any tested budget, and same-base adaptive variants hurt or were neutral in 11/15 budget-by-base comparisons.
- V13.10 reconciled the apparent V13.9/V13.10 metric mismatch. On this dataset, temporal-overlap event hits and direct stitched-event discovery produce identical deterministic results. The apparent mismatch came from comparing against the wrong V13.9 CSV field and from a random-method aggregation bug in the comparison script.

## 4. What Has Failed

- The cheap handcrafted proxies tested so far, mainly YOLO vehicle/object counts, bounding-box geometry, center-region counts, and motion energy, do not provide useful low-budget event recovery on the unbiased V13.8 full reference.
- V13.7's optimistic labeled-subset replay is superseded as current performance evidence. The subset was pilot-derived and high-YOLO-biased, so its recall advantages were inflated compared with V13.9/V13.10 full-reference evaluation.
- Simple adaptive search did not rescue weak proxy scores. The evidence supports the narrower claim that these adaptive mechanisms fail under the current proxy family, not that adaptive query execution is impossible.
- Nexar-200 derived-boundary labels failed as an oracle-relative benchmark for this predicate. The VLM micro-audit reported only 0.160 positive agreement, so those labels are `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`.
- Micro-CASQ certificate work remains underpowered. V12.1 had 38 eligible positives; Phase 0.6 power simulation suggests hundreds of events are needed for non-vacuous certificates under its assumptions.

## 5. What Is Still Uncertain

- Whether representation-based scoring, such as RoI-SigLIP or CLIP-like embeddings, can rank ego-path conflict better than traffic density.
- Whether an 8B VLM or other mid-fidelity semantic scorer can serve as a useful L1/L2 allocation signal before 32B oracle calls.
- Whether ego-path-conditioned geometric features, using lane/path and object trajectory intersection, can directly target the predicate better than raw object counts.
- Whether the V13.6 prompt and V13.8 positive rate generalize beyond one 66.5-minute video.
- Whether Qwen3-VL-32B labels are stable or calibrated to human judgment. No human-adjudicated label set currently exists.
- Whether the certificate layer can produce non-vacuous oracle-relative guarantees on a valid full-reference benchmark. The strongest current V13 result is a reference and negative selection result, not a certificate.

## 6. Strongest Evidence Artifacts

- `repo_audit_for_codex_v1/EVIDENCE_PACK.md`: consolidated status, safe numbers, failed claims, and risks.
- `repo_audit_for_codex_v1/EXPERIMENT_LINEAGE.md`: dependency chain and superseded conclusions.
- `repo_audit_for_codex_v1/DECISION_LOG.md`: extracted decision strings with validity status.
- `repo_audit_for_codex_v1/KEY_RESULTS_TABLE.csv`: quantitative summary across V13.5 through V13.10 and supporting work.
- `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/reports/FINAL_REPORT.md`: strongest oracle-reference report.
- `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv`: 399 anchor labels, the V13 source of truth.
- `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_vlm_oracle_events.csv`: 51 stitched VLM-defined events.
- `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/reports/FINAL_REPORT.md`: full-reference static AQP failure.
- `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`: OracleBest, efficiency audit, adaptive simulation, and sensitivity addenda.
- `test_vlm/outputs/v13_10/reports/V13_10_MISMATCH_ROOT_CAUSE.md`: metric reconciliation.

## 7. Single-Video-Only Results

All V13.5 through V13.10 results are from `realcartest.mp4`, a single approximately 66.5-minute dashcam video. The following must not be generalized to all driving videos without a second-video benchmark:

- 399 center10 anchors.
- 94 positive anchors and 51 stitched events.
- 23.6% positive-anchor rate.
- 0% abstain under the repaired V13.6 prompt.
- 100% complete event visibility and 0% truncation.
- Weak low-budget recall from cheap proxy methods.
- Adaptive search underperformance under current proxy scores.

## 8. VLM-Oracle-Relative Results

All V13.x event labels and recall metrics are relative to Qwen3-VL-32B outputs, not human truth. This includes:

- V13.5 pilot labels.
- V13.6 construction labels.
- V13.8 full center10 oracle labels.
- V13.9 static method recall.
- V13.10 OracleBest, static efficiency, adaptive simulation, and metric reconciliation.

No human-adjudicated ground-truth recall number exists in the audited evidence.

## Stage-by-Stage Summary

### V13.5

- Goal: Pilot whether `realcartest.mp4` contains enough `O_enter_ego_path_v0` positives for a full benchmark.
- Method: 100 Qwen3-VL-32B calls on 5s pilot clips using the older prompt.
- Key results: 18% positive pilot rate, 66% abstain.
- Final decision: `PROCEED_FULL_ORACLE` gate in lineage, but the abstain behavior required repair.
- Current validity: partially_valid. The pilot established signal, but the old-prompt abstain rate is superseded by V13.6.

### V13.6

- Goal: Compare clip construction policies and repair the abstain problem.
- Method: 416 VLM calls, 52 base clips by 8 policies.
- Key results: `center_10s` produced 29 positives out of 52, 56% positive rate, 0 abstain, 399 estimated full-video calls versus 798 fixed 5s calls, and 100% complete event visibility.
- Final decision: `FINAL_DECISION: USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE`.
- Current validity: valid for this single-video VLM-oracle-relative setting.

### V13.7

- Goal: Replay multiple selection methods on existing center10 labels without new VLM calls.
- Method: 17 methods by 8 budgets over a 52-clip labeled subset from V13.6.
- Key results: Proxy methods appeared to beat random by at least +0.10 on the labeled subset; best B=20 labeled-subset recall was 0.448.
- Final decision: `FINAL_DECISION: CENTER10_FULL_REFERENCE_RECOMMENDED`.
- Current validity: superseded as performance evidence. The recommendation to build V13.8 was correct, but the proxy-performance numbers are biased and should not be cited as current evidence.

### V13.8

- Goal: Construct a full center10 VLM-oracle-relative reference.
- Method: Qwen3-VL-32B on all 399 center10 anchors using the repaired V13.6 prompt.
- Key results: 399/399 successful calls, 94 positives, 305 negatives, 0 abstain, 51 stitched events, 100% complete events, 0% truncation, about 74 minutes runtime.
- Final decision: `V13_8_DECISION: FULL_CENTER10_ORACLE_REFERENCE_READY`.
- Current validity: valid. This is the strongest current source of labels for V13.9/V13.10.

### V13.9

- Goal: Evaluate latency-aware, budgeted static query plans on the full V13.8 oracle.
- Method: 19 methods by 5 budgets over the 399-anchor reference.
- Key results: Best B=20 method was `uniform_anchor_10s` with temporal-overlap event recall 0.137; best B=40 was `top_fusion_geometry_motion` with recall 0.216; proxy delta versus random at B=20 was +0.059, below the +0.10 threshold.
- Final decision: `V13_9_DECISION: LATENCY_AWARE_AQP_FAIL`.
- Current validity: valid, confirmed by V13.10 metric reconciliation. Use the `event_recall_overlap` field, not IoU recall fields.

### V13.10

- Goal: Compute OracleBest upper bound, efficiency ratios, adaptive search results, and reconcile metrics.
- Method: Direct event-discovery OracleBest over 51 stitched events; static efficiency audit; priority-boost and bidirectional-expansion adaptive simulations; mismatch root-cause analysis.
- Key results: OracleBest@B = min(B,51)/51; static B=20 best efficiency 0.350; static B=40 best efficiency 0.275; adaptive never beat best static; same-base adaptive hurt or was neutral at 11/15 budget-by-base combinations; V13.9/V13.10 event-hit definitions were semantically equivalent on this dataset.
- Final decisions: `STATIC_METHODS_FAR_BELOW_UPPER_BOUND`, `ADAPTIVE_NO_BETTER`, `SAME_BASE_HURTS_CONSISTENTLY`, `V13_10_COMPARISON_BUG_NOT_SEMANTIC_DIFFERENCE`.
- Current validity: valid, with the explicit scope that this is exploratory, single-video, VLM-oracle-relative, and not a certificate run.
