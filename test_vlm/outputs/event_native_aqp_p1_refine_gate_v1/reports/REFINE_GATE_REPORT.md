# P1 REFINE Gate — No-New-VLM REFINE Replay Report

**Date:** 2026-06-25
**Data source:** V13.8 full oracle labels (399 anchors, 94 positive, 51 stitched events)
**Method:** Read-only CSV replay over existing V13.8 labels. No new VLM/YOLO/GPU calls.

---

## 1. Replay Design

For each of the 94 positive anchors, three strategies are simulated:

| Strategy | Description |
|---|---|
| `candidate_only` | Use the anchor's own event boundary [event_start_abs, event_end_abs] (typically 0.7s) |
| `candidate_plus_boundary` | Check left/right neighbor anchor labels. If neighbor is positive, extend the event boundary to include the neighbor's event interval. Simulates spending 1–2 extra oracle calls on neighbors. |
| `candidate_plus_stitch` | Use the full stitched event boundary (reference). This is the upper bound of what neighbor-based extension can achieve. |

**Reference boundary:** The 51 stitched events from `center10_vlm_oracle_events.csv`.

**Metrics:** event_iou, start_boundary_error, end_boundary_error, mean_boundary_error, over_expansion, fragmentation.

---

## 2. Headline Counts

| Metric | Value |
|---|---|
| Evaluable candidates (positive anchors with event boundary) | **94** |
| Positive candidates | **94** |
| Candidates with left neighbor label | 93 (1 anchor at index 0 has no left neighbor) |
| Candidates with right neighbor label | 94 |
| Candidates with reference boundary (stitched event) | 94 |
| Candidates with left boundary neighborhood label | 93 |
| Candidates with right boundary neighborhood label | 94 |

---

## 3. Event Boundary Degeneracy

**Critical precondition:** Before interpreting replay results, the event boundary quality must be assessed.

| Pattern | Count | % of 94 positives |
|---|---|---|
| event_start = 0.0 (clip start) | 85 | **90.4%** |
| event_end = 0.7 | 93 | 98.9% |
| Both (0.0, 0.7) | 85 | **90.4%** |
| event_start_absolute == clip start_time | 85 | 90.4% |

All event durations: 0.2–1.0s (mean 0.66s) within 10s clips.

**Interpretation:** The VLM reports events as starting at the clip beginning with ~0.7s duration in 90% of cases. This is a degenerate pattern — the VLM is not measuring the actual event boundary within the clip; it is producing a default "event at clip start, 0.7s duration" response. This means the "candidate_only" event boundary is not a real measurement of the event's temporal extent.

---

## 4. Replay Results — Aggregate

| Metric | candidate_only | candidate_plus_boundary | candidate_plus_stitch |
|---|---:|---:|---:|
| Mean event IoU vs reference | 0.362 | **0.811** | 1.000 |
| Mean start boundary error (s) | 11.370 | **5.529** | 0.000 |
| Mean end boundary error (s) | 11.370 | **5.529** | 0.000 |
| Mean boundary error (s) | 11.370 | **5.529** | 0.000 |

| Outcome | Count |
|---|---|
| Improved (IoU increased) | **62** |
| Worsened (IoU decreased) | **0** |
| Unchanged (IoU same) | **32** |

**At first glance, boundary refinement improves IoU from 0.362 to 0.811 with 62 improvements and 0 worsened. However, this is misleading — see Section 5.**

---

## 5. Split by Event Type — The Critical Finding

### 5.1 Single-anchor events (32 candidates)

| Metric | candidate_only | candidate_plus_boundary |
|---|---:|---:|
| Mean event IoU | **1.000** | **1.000** |
| Mean boundary error (s) | **0.000** | **0.000** |
| Outcome | All 32 unchanged |

**For single-anchor events, boundary refinement does nothing.** The candidate already matches the reference (both are the same 0.7s event). Neighbor labels are negative (otherwise the event would be multi-anchor), so no extension occurs. IoU is already 1.0.

### 5.2 Multi-anchor events (62 candidates)

| Metric | candidate_only | candidate_plus_boundary |
|---|---:|---:|
| Mean event IoU | **0.033** | **0.713** |
| Mean start boundary error (s) | 17.238 | 8.384 |
| Mean end boundary error (s) | 17.238 | 8.384 |
| Mean boundary error (s) | 17.238 | 8.384 |
| Outcome | All 62 improved |

**For multi-anchor events, boundary refinement "improves" IoU from 0.033 to 0.713. But this improvement is entirely due to over-expansion, not precision.**

---

## 6. Over-expansion and Fragmentation Analysis

### 6.1 Over-expansion

| Metric | Value |
|---|---|
| Cases with over-expansion (>2s extra duration) | **62 / 62 improved** |
| Mean over-expansion per improved case | See below |

**All 62 "improved" cases are over-expansion cases.** The boundary refinement extends the candidate from a 0.7s event to cover the entire stitched span (up to 90.7s). For example:
- `realcartest_event_0000`: 10 anchors, each reporting a 0.7s event. Stitched span = 90.7s. Actual event time = 10 × 0.7s = 7s. Over-expansion = 83.7s (92.3% of the span is non-event time).
- The "improved" IoU of 0.713 means the refined candidate covers 71.3% of the stitched span, but the stitched span itself is 92.3% non-event time.

**This is not boundary quality improvement — it is matching an over-expanded reference.**

### 6.2 Fragmentation

| Metric | Value |
|---|---|
| Fragmentation cases (multi-anchor event with <1s individual events) | **62** |

The 62 multi-anchor events are inherently fragmented: each anchor reports a separate 0.7s event, but stitching merges them into one span. The 0.7s events are 10s apart (at clip boundaries), creating gaps of ~9.3s between events. Boundary refinement at 10s resolution cannot resolve this fragmentation — it can only extend to cover the gaps, which is over-expansion.

### 6.3 False positive rejection

| Metric | Value |
|---|---|
| False positives rejected by boundary/context observation | **0** |
| Neighbor disagreement cases (center positive, left neighbor negative) | **42** |

42 positive anchors have a negative left neighbor with the event starting at clip boundary (event_start = 0.0). This could indicate:
1. The event genuinely starts at the clip boundary (possible but unlikely for 42/94 = 45% of positives)
2. The VLM is producing a boundary artifact (event reported at clip start regardless of actual timing)

**Without sub-clip observations, we cannot determine which interpretation is correct.** The existing neighbor labels (binary positive/negative on 10s clips) cannot confirm or reject false positives.

---

## 7. Why the "Improvement" Is Not Real REFINE Evidence

### 7.1 The improvement is circular

The "reference" boundary is the stitched event, which is constructed by merging consecutive positive anchors. The "boundary refinement" extends the candidate to include consecutive positive neighbors. These are the same operation — the "improvement" is tautological.

### 7.2 The reference is over-expanded

The stitched event [10.0, 100.7] is 90.7s long but contains only 7s of actual event time (10 × 0.7s events). Matching this reference means the candidate is also over-expanded. A higher IoU against an over-expanded reference is NOT quality improvement.

### 7.3 The event boundaries are degenerate

90.4% of positives have event_start = 0.0, event_end = 0.7. There is no boundary variation to refine. The VLM is not measuring the event boundary — it is producing a default response. True boundary refinement requires the VLM to report different boundaries for different events, which is not the case.

### 7.4 No sub-clip observations exist

All labels are on 10s clips (or 4–20s clips in V13.6). No 2s sub-clip observations near event boundaries exist. The existing data can only test "does extending to neighbors improve coverage?" (yes, but via over-expansion), not "does observing near the boundary improve precision?" (untestable).

### 7.5 H3 (confirmed-positive refine) already failed

The diversity_prefilter replay tested H3: expanding ±30/±60s around confirmed positives. Result: **FAILED** (recall 0.098 at B=20 vs base 0.157). Reason: positives are temporally clustered, so expanding around confirmed positives re-hits already-hit neighborhoods. This is directly relevant — it shows that neighborhood-level refinement on this data does not discover new events.

---

## 8. Stability Assessment

| Question | Answer |
|---|---|
| Is the improvement stable across multiple candidates? | **No** — improvement only occurs for multi-anchor events (62/94), and all improvements are over-expansion |
| Is the improvement stable across event types? | **No** — single-anchor events (32/94) show zero improvement |
| Does the improvement reduce boundary error? | **Misleading** — boundary error decreases from 17.2s to 8.4s for multi-anchor events, but this is because the candidate is extended to cover the over-expanded reference, not because the boundary is more precise |
| Does the improvement reject false positives? | **No** — 0 false positives rejected; 42 neighbor-disagreement cases unresolved |
| Does the improvement reduce over-expansion? | **No** — it causes over-expansion (62/62 improved cases are over-expansion) |
| Does the improvement reduce fragmentation? | **No** — it masks fragmentation by covering gaps with over-expanded spans |

---

## 9. Failure Cases

| Case | Count | Description |
|---|---|---|
| Degenerate boundary (0.0–0.7) | 85/94 | VLM reports event at clip start with 0.7s regardless of actual timing |
| Over-expansion from neighbor extension | 62/94 | Extending to positive neighbors creates over-expanded spans |
| Fragmentation in multi-anchor events | 62/94 | Individual 0.7s events 10s apart within stitched spans |
| Neighbor disagreement unresolved | 42/94 | Center positive, left neighbor negative, event at clip start — potential false positive or boundary artifact |
| Sub-clip boundary observation absent | 94/94 | No 2s refinement observations exist for any candidate |
| V13.7 shifted observations non-overlapping | 52/52 | 0/52 V13.7 center times overlap with V13.8 anchor times (different centers, same degenerate pattern) |

---

## 10. REFINE Gate Verdict

### 10.1 Can boundary observations improve event IoU?

**Technically yes, but only via over-expansion.** The IoU improvement from 0.033 to 0.713 for multi-anchor events is real numerically, but it is achieved by extending the candidate to match the over-expanded stitched reference. This is not boundary quality improvement.

### 10.2 Can boundary observations reduce start/end error?

**Misleading.** Boundary error decreases from 17.2s to 8.4s for multi-anchor events, but this is because the extended candidate covers more of the over-expanded span, not because the boundary is more precise. The actual event boundary (0.7s) is not refined.

### 10.3 Can boundary observations correct false positives, over-expansion, or fragmentation?

**No.**
- 0 false positives rejected (no sub-clip observations to verify)
- Over-expansion is caused, not corrected (62/62 improved cases are over-expansion)
- Fragmentation is masked, not corrected (gaps covered by over-expanded spans)

### 10.4 Are improvements stable across candidates?

**No.** Improvement only occurs for multi-anchor events (62/94) and is entirely over-expansion. Single-anchor events (32/94) show zero improvement.

### 10.5 Overall REFINE assessment

**The existing data does not support REFINE as a boundary quality improvement.** The only available "refinement" (neighbor label extension) is equivalent to stitching, which creates over-expansion. True boundary refinement requires sub-clip observations (e.g., 2s VLM calls near event boundaries) that do not exist in the repository.

---

## 11. Files Produced by This Replay

| File | Description |
|---|---|
| `refine_candidate_audit_table.csv` | 94-row candidate audit table |
| `refine_replay_metrics.csv` | 94-row per-candidate replay metrics |
| `refine_replay_aggregates.json` | Aggregate replay statistics |
| `run_refine_gate_analysis.py` | Analysis script (read-only on existing CSVs) |
