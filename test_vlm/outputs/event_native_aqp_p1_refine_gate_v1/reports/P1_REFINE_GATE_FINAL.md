# P1 REFINE Gate — Final Report

**Date:** 2026-06-25
**Project:** Event-Native Budgeted AQP for Semantic Event Clip Queries
**Task:** P1 REFINE Gate
**Video:** realcartest.mp4 (~66.5 min, single video, VLM-oracle-relative)

---

## 1. Task Objective

Determine whether, near existing candidate events, a small number of additional boundary observations can improve event boundary quality (event IoU, start/end boundary error, candidate fragmentation). If existing data cannot answer this, generate a minimal oracle supplementation plan without executing it.

The active predicate is `O_enter_ego_path_v0`. All labels are VLM-oracle-relative (Qwen3-VL-32B), not human truth.

---

## 2. New Files Produced

All files under `test_vlm/outputs/event_native_aqp_p1_refine_gate_v1/`:

| File | Type | Description |
|---|---|---|
| `refine_candidate_audit_table.csv` | CSV (94 rows) | Candidate-level audit table with 26 fields per candidate |
| `refine_replay_metrics.csv` | CSV (94 rows) | Per-candidate REFINE replay metrics (candidate_only vs boundary_refined vs stitch) |
| `refine_replay_aggregates.json` | JSON | Aggregate replay statistics |
| `refine_minimal_oracle_plan.csv` | CSV (68 rows) | Minimal oracle supplementation plan (not executed) |
| `run_refine_gate_analysis.py` | Python | Read-only analysis script (no model calls) |
| `reports/ASSET_MAP.md` | Markdown | Asset inventory and usability assessment |
| `reports/REFINE_GATE_REPORT.md` | Markdown | No-new-VLM REFINE replay report |
| `reports/MINIMAL_ORACLE_PLAN.md` | Markdown | Minimal oracle plan rationale and design |
| `reports/P1_REFINE_GATE_FINAL.md` | Markdown | This final report |

No existing files were modified, overwritten, moved, or deleted.

---

## 3. Asset Inventory Summary

### Primary assets
- **V13.8 full oracle labels** (`experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv`): 399 center10 anchors, 94 positive / 305 negative / 0 abstain, Qwen3-VL-32B, ~74 min GPU. All 399 anchors labeled (full scan, not budgeted).
- **V13.8 stitched events** (`center10_vlm_oracle_events.csv`): 51 events (32 single-anchor, 19 multi-anchor). Reference boundaries.
- **V13.7 proxy features** (`center10_proxy_features.csv`): 399 anchors with YOLO/motion/geometry proxy scores. `object_count_mean` is best single feature (AUC 0.738).

### Secondary assets (not usable for REFINE)
- **V13.6 clip construction** (416 labels, 8 policies): Same degenerate boundary pattern (83.8% event_start=0.0). Different center times, no overlap with V13.8 anchors.
- **V13.5 pilot** (100 labels): No event boundary fields. Binary labels only.
- **V13.9/V13.10 budget replay**: Shows IoU=0 at all thresholds, confirming clip-level IoU is not meaningful for 0.7s events in 10s clips.
- **Diversity prefilter H3**: Confirmed-positive refine ±30/±60s already FAILED (recall 0.098 vs base 0.157 at B=20).

### Boundary refinement prior work
- `agent_loop_center10_v13_8_to_v13_9_FINAL.md` (line 71): proposed "2s refinement VLM" — never executed.
- `CURRENT_PROJECT_STATE_READONLY_AUDIT.md` (line 178): "boundary 2s 精修未测" (boundary 2s refinement not tested).
- No sub-clip (2s) VLM observations exist anywhere in the repository.

**ASSET_DECISION: INSUFFICIENT_LABELS_NEED_MINIMAL_ORACLE_PLAN**

---

## 4. Candidate Audit Table Summary

| Metric | Value |
|---|---|
| Total candidates (positive anchors) | 94 |
| With left neighbor label | 93 |
| With right neighbor label | 94 |
| With reference boundary (stitched event) | 94 |
| Can evaluate candidate_only | 94 (100%) |
| Can evaluate boundary_refine | 94 (100%) |
| Can evaluate stitch/context | 62 (66%, multi-anchor events) |
| With V13.7 shifted observation nearby | 0 (0/52 overlap with V13.8 anchors) |
| With V13.6 multi-window observation nearby | 23/52 within 5s (but same degenerate pattern) |
| With sub-clip (2s) boundary observation | **0** |

The audit table was constructed by joining V13.8 oracle labels (event boundaries, labels), V13.7 proxy features (proxy scores), and V13.8 stitched events (reference boundaries). Neighbor labels were obtained from the V13.8 full scan (all 399 anchors labeled at 10s stride). No fields were fabricated; unavailable fields are left empty with explanation in `notes`.

---

## 5. No-New-VLM REFINE Replay Feasibility

**Technically feasible:** Yes. All 94 positive anchors have neighbor labels (full oracle scan). A replay comparing candidate_only, candidate_plus_boundary, and candidate_plus_stitch was completed.

**Meaningfully answerable:** No. The replay was completed and results computed, but the results demonstrate that existing data cannot meaningfully answer the REFINE question (see Section 6).

---

## 6. REFINE Replay Results — Is REFINE Supported by Existing Data?

### 6.1 Headline numbers

| Metric | candidate_only | candidate_plus_boundary |
|---|---:|---:|
| Mean event IoU | 0.362 | 0.811 |
| Improved | — | 62 / 94 |
| Worsened | — | 0 / 94 |
| Unchanged | — | 32 / 94 |

### 6.2 The critical split

| Event type | n | IoU (cand_only) | IoU (boundary) | Improvement? |
|---|---|---:|---:|---|
| Single-anchor | 32 | 1.000 | 1.000 | **None** (already perfect) |
| Multi-anchor | 62 | 0.033 | 0.713 | **Over-expansion** (see below) |

### 6.3 Why the improvement is not real

1. **All 62 "improved" cases are over-expansion.** The boundary refinement extends the 0.7s candidate to cover the entire stitched span (up to 90.7s). The stitched span contains only 7s of actual event time (10 × 0.7s). The refined candidate is 92.3% non-event time. Higher IoU against an over-expanded reference is NOT quality improvement.

2. **The improvement is circular.** The reference (stitched event) is constructed by merging consecutive positive anchors. The boundary refinement extends the candidate to include consecutive positive neighbors. These are the same operation.

3. **Event boundaries are degenerate.** 90.4% of positives have event_start=0.0, event_end=0.7. There is no boundary variation to refine. The VLM is not measuring boundaries; it is producing a default response.

4. **No false positive rejection.** 0/94 false positives rejected. 42 candidates have center positive + left neighbor negative + event at clip start — potential boundary artifacts that cannot be verified without sub-clip observations.

5. **Fragmentation is masked, not corrected.** 62 multi-anchor events are fragmented (0.7s events 10s apart). Boundary refinement covers the gaps with over-expanded spans, masking the fragmentation.

6. **Single-anchor events show zero improvement.** 32/94 candidates (34%) have IoU=1.0 for both strategies. Neighbor labels are negative, so no extension occurs. There is nothing to refine.

### 6.4 Conclusion

**REFINE is NOT supported by existing data.** The only available "refinement" (neighbor label extension) is equivalent to stitching and creates over-expansion. True boundary refinement requires sub-clip observations that do not exist.

---

## 7. Minimal Oracle Plan Summary

Since existing data is insufficient, a minimal oracle plan was generated (68 calls, not executed):

| Call type | Count | Priority | Purpose |
|---|---|---|---|
| left_boundary | 29 | 1–2 | 2s sub-clip at event start: test if 0.0 is real or VLM artifact |
| right_boundary | 19 | 1 | 2s sub-clip at event end: test if 0.7 is real or VLM artifact |
| stitch_context | 9 | 1 | 10s sub-clip at mid-gap: test if multi-anchor events are continuous or fragmented |
| ambiguity | 10 | 3 | 4s sub-clip at neg→pos boundary: test if positive is genuine or boundary artifact |
| hard_negative | 1 | 4 | 4s sub-clip: VLM label consistency baseline |
| **Total** | **68** | | **~12.7 min GPU estimated** |

The plan targets the 19 multi-anchor events (highest over-expansion) as priority 1, and 10 single-anchor truncated-left events as priority 2. The goal is to determine whether sub-clip observations can:
1. Provide more precise event boundaries than the degenerate 0.0–0.7 pattern
2. Resolve whether multi-anchor events are continuous or fragmented
3. Detect false positives at clip boundaries

---

## 8. Recommendation for Next Steps

1. **Do NOT proceed with REFINE using existing data alone.** The replay shows that the only available refinement (neighbor extension) creates over-expansion, not quality improvement.

2. **Execute the minimal oracle plan (68 calls, ~13 min GPU)** — if authorized — to generate sub-clip boundary observations. This is the minimum needed to test whether boundary observations can improve event boundary quality.

3. **If the minimal oracle plan shows sub-clip observations provide different boundaries** (e.g., event_start ≠ 0.0 at 2s resolution), then REFINE is worth pursuing with a larger experiment.

4. **If the minimal oracle plan shows the same degenerate pattern at 2s resolution**, then the VLM cannot measure event boundaries at any resolution, and REFINE should be abandoned in favor of clip-level (not boundary-level) AQP methods.

5. **Do NOT use the over-expanded stitched events as reference boundaries.** If the stitch_context calls show mid-gap is negative, the stitched events must be split into separate events before any IoU evaluation.

6. **Consider alternative reference construction.** Instead of stitching (which over-expands), consider using the individual anchor event boundaries as the reference, and test whether sub-clip observations can improve IoU against those.

---

## 9. Limitations

1. **Single video.** All findings are for `realcartest.mp4` only. No generalization claim.
2. **VLM-oracle-relative.** Qwen3-VL-32B labels are not human truth. No human calibration exists.
3. **Degenerate boundaries.** The 90.4% event_start=0.0 pattern may be specific to this VLM/prompt/video combination. A different VLM or prompt might produce more varied boundaries.
4. **No sub-clip observations.** The inability to test true boundary refinement is a data gap, not a theoretical limitation.
5. **H3 failure.** The diversity_prefilter H3 result (expanding around confirmed positives fails) is relevant but tests a different question (discovery, not boundary refinement).

---

## 10. Final Decision

The existing data supports a no-new-VLM replay, but the replay demonstrates that:
- The only available "refinement" (neighbor label extension) creates over-expansion, not boundary quality improvement
- Event boundaries are degenerate (90.4% have 0.0–0.7 pattern) with no variation to refine
- No sub-clip boundary observations exist to test true boundary refinement
- The reference boundaries (stitched events) are over-expanded artifacts
- 0 false positives can be rejected; 42 potential boundary artifacts remain unresolved

Therefore, a minimal oracle plan (68 calls) is needed before REFINE can be meaningfully evaluated.

FINAL_DECISION: NEED_MINIMAL_ORACLE_BEFORE_REFINE
