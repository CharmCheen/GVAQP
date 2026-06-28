# P1 REFINE Gate — Minimal Oracle Plan

**Date:** 2026-06-25
**Status:** PLAN ONLY — no oracle calls executed. No VLM/YOLO/GPU calls made.

---

## 1. Why Existing Data Is Insufficient

The no-new-VLM REFINE replay (see `REFINE_GATE_REPORT.md`) demonstrates that existing data cannot meaningfully answer whether boundary observations improve event clip quality. The specific insufficiencies are:

### 1.1 Degenerate event boundaries
90.4% of positive anchors (85/94) have event_start = 0.0 and event_end = 0.7. The VLM reports events at clip start with 0.7s duration regardless of actual event timing. This is a VLM behavior artifact, not a boundary measurement. There is no boundary variation to refine.

### 1.2 No sub-clip boundary observations
All 399 existing VLM labels are on 10s center clips. No 2s (or other sub-clip) observations near event boundaries exist. The `agent_loop_center10_v13_8_to_v13_9_FINAL.md` (line 71) proposed "2s refinement VLM" but it was never executed. `CURRENT_PROJECT_STATE_READONLY_AUDIT.md` (line 178) confirms: "boundary 2s 精修未测".

### 1.3 Over-expanded reference
The 51 stitched events (reference boundaries) are over-expanded: 19 multi-anchor events merge consecutive 0.7s events into spans up to 90.7s. Matching this reference via neighbor extension is over-expansion, not quality improvement.

### 1.4 Neighbor labels are binary only
The existing neighbor observations are binary (positive/negative on 10s clips). They can tell whether an adjacent clip contains an event, but cannot tell where the event boundary is within that clip.

### 1.5 V13.7/V13.6 shifted observations do not help
V13.7 has 52 labels at shifted center times, but 0/52 overlap with V13.8 anchor times, and they exhibit the same degenerate 0.0–0.7 boundary pattern. V13.6 has 416 labels at different clip window sizes (4–20s), but event_start is still 0.0 in 83.8% of positives.

### 1.6 H3 (confirmed-positive refine) already failed
The diversity_prefilter replay tested expanding ±30/±60s around confirmed positives. Result: FAILED (recall 0.098 at B=20 vs base 0.157). Neighborhood-level refinement on this data re-hits already-hit events.

---

## 2. Minimum Oracle Calls Needed

**Total proposed calls: 68**

This is the minimum to answer the core REFINE question: "Can sub-clip boundary observations improve event boundary quality?"

| Call type | Count | Purpose |
|---|---|---|
| left_boundary | 29 | 2s sub-clip at event start boundary: test if event truly starts at clip start or is VLM artifact |
| right_boundary | 19 | 2s sub-clip at event end boundary: test if event truly ends at 0.7s or extends further |
| stitch_context | 9 | 10s sub-clip at mid-gap of multi-anchor events: test if event is continuous or fragmented |
| ambiguity | 10 | 4s sub-clip at boundary between positive and negative anchor: test if positive is genuine or boundary artifact |
| hard_negative | 1 | 4s sub-clip at neg→pos boundary: test VLM label consistency at 2s resolution |
| **Total** | **68** | |

**Estimated cost:** 68 × ~11.2s/call ≈ 12.7 minutes GPU time (based on V13.8 mean runtime 11.2s/call for Qwen3-VL-32B on 10s clips; 2s clips should be faster).

---

## 3. Purpose of Each Call Type

### 3.1 left_boundary (29 calls, Priority 1 + 2)

**What:** For each multi-anchor event's first anchor and each single-anchor event with truncation_left, run VLM on a 2s sub-clip centered on event_start_absolute.

**Why:** 85/94 positives have event_start = 0.0 (clip start). This could mean:
- (a) The event genuinely starts at the clip boundary
- (b) The VLM defaults to 0.0 when it cannot precisely localize the event start

A 2s sub-clip at [event_start_abs - 1, event_start_abs + 1] will show whether the event is visible at this finer resolution. If the 2s sub-clip reports a different event_start (e.g., 0.5 or 1.0), it means the VLM can localize boundaries at 2s resolution and the 0.0 pattern is a 10s-clip artifact. If it still reports 0.0, the degenerate pattern persists at finer resolution.

**Expected outcome:** This directly tests whether boundary observations can improve event_start precision.

### 3.2 right_boundary (19 calls, Priority 1)

**What:** For each multi-anchor event's last anchor, run VLM on a 2s sub-clip centered on event_end_absolute.

**Why:** 93/94 positives have event_end = 0.7. Similar to left_boundary, this tests whether the event end can be localized more precisely with a 2s observation.

**Expected outcome:** Tests whether event_end precision improves with sub-clip observations.

### 3.3 stitch_context (9 calls, Priority 1)

**What:** For multi-anchor events with ≥3 anchors, run VLM on a 10s sub-clip centered on the gap between the first and last anchor (mid-event).

**Why:** The stitched event [10.0, 100.7] assumes the event is continuous across all 10 anchors. But each anchor only reports a 0.7s event. The mid-gap observation tests whether the intermediate time is truly positive (continuous event) or negative (fragmented separate events).

**Expected outcome:** Directly tests the fragmentation hypothesis. If mid-gap is negative, the stitched event is over-expanded and should be split into separate events.

### 3.4 ambiguity (10 calls, Priority 3)

**What:** For 10 single-anchor positives with event_start = 0.0 and negative left neighbor, run VLM on a 4s sub-clip at [event_start_abs - 3, event_start_abs + 1].

**Why:** 42/94 positives have this pattern (center positive, left neighbor negative, event at clip start). This could be:
- (a) A genuine event that starts exactly at the clip boundary
- (b) A VLM boundary artifact (the VLM reports "positive" when an event is near the clip edge, even if the event is actually in the previous clip)

The 4s sub-clip spans the boundary between the negative and positive anchors. If the event is visible in the portion that belongs to the "negative" anchor, it suggests the VLM's 10s labels are inconsistent at boundaries.

**Expected outcome:** Tests false positive rejection capability of boundary observations.

### 3.5 hard_negative (1 call, Priority 4)

**What:** 4s sub-clip at the boundary between a negative and positive anchor.

**Why:** Tests VLM label consistency at 2s resolution. If the VLM gives different labels for the same frames depending on the clip window, the boundary observations are unreliable.

**Expected outcome:** Baseline label consistency check.

---

## 4. What Questions Can Be Answered

With the 68 proposed oracle calls, the following questions can be answered:

| Question | Call type | Answer mechanism |
|---|---|---|
| Can 2s sub-clip observations provide more precise event_start than the 0.0 default? | left_boundary | Compare 2s event_start vs 10s event_start |
| Can 2s sub-clip observations provide more precise event_end than the 0.7 default? | right_boundary | Compare 2s event_end vs 10s event_end |
| Are multi-anchor events continuous or fragmented? | stitch_context | Check if mid-gap is positive (continuous) or negative (fragmented) |
| Are boundary positives genuine or VLM artifacts? | ambiguity | Check if event is visible in the "negative" side of the boundary |
| Is the VLM consistent at 2s resolution? | hard_negative | Compare 2s label with 10s label for same time range |

**What questions CANNOT be answered with 68 calls:**
- Statistical significance of boundary improvement (need more candidates)
- Generalization to other videos (single video only)
- Human-truth quality of the boundaries (VLM-oracle-relative only)
- Whether boundary refinement improves downstream AQP recall (need full pipeline test)

---

## 5. Priority Ranking

| Priority | Count | Criteria |
|---|---|---|
| 1 | 47 | Multi-anchor event boundary + mid-gap: directly tests over-expansion and fragmentation (the two main findings) |
| 2 | 10 | Single-anchor truncation_left: tests degenerate boundary pattern on isolated events |
| 3 | 10 | Ambiguity / potential false positive: tests false positive rejection |
| 4 | 1 | Hard negative: label consistency baseline |

### Top priority candidates

The highest-priority calls are for the 19 multi-anchor events, specifically:
- `realcartest_event_0000` (10 anchors, 90.7s span): 3 calls (left, right, mid-gap)
- `realcartest_event_0037` (6 anchors, 50.7s span): 3 calls
- `realcartest_event_0015` (5 anchors, 40.7s span): 3 calls
- `realcartest_event_0006` (4 anchors, 30.7s span): 3 calls
- `realcartest_event_0014` (4 anchors, 30.2s span): 3 calls
- `realcartest_event_0042` (4 anchors, 30.7s span): 3 calls
- ... and 13 more 2–3 anchor events

These events have the most over-expansion and are the strongest test cases for whether boundary refinement can improve quality.

---

## 6. Execution Plan (NOT EXECUTED)

**This plan is provided for review only. No oracle calls are executed.**

If authorized, the execution would be:

1. Extract 2s/4s sub-clips from `realcartest.mp4` at the proposed timestamps
2. Run Qwen3-VL-32B with V13.6 prompt on each sub-clip
3. Compare sub-clip event_start/end with 10s event_start/end
4. Compute refined event IoU using sub-clip boundaries as reference
5. Test over-expansion: if mid-gap calls return negative, split multi-anchor events
6. Test false positive: if ambiguity calls show event in negative-anchor territory, flag boundary artifacts

**Estimated GPU time:** ~12.7 minutes (68 calls × 11.2s/call, conservative estimate)
**Output directory:** `test_vlm/outputs/event_native_aqp_p1_refine_gate_v1/oracle_supplement_v1/` (if authorized)

---

## 7. File Reference

| File | Description |
|---|---|
| `refine_minimal_oracle_plan.csv` | 68-row plan with candidate_id, timestamp, reason, priority |
