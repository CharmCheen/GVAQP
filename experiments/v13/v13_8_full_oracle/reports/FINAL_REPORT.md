# V13.8 Final Report — Full Center10 Oracle Reference

**Date:** 2026-06-23

## 1. Goal

Construct a full VLM-oracle-relative reference for all 399 center10 anchors on realcartest.mp4.

## 2. Method

- Qwen3-VL-32B-Instruct, NVIDIA A800-SXM4-80GB, bfloat16
- V13.6 prompt (O_enter_ego_path_v0, negative-not-abstain rule)
- All 399 center10 anchors: [anchor−5s, anchor+5s], 2fps
- Total runtime: ~74 minutes

## 3. Results

| Metric | Value |
|---|---|
| Total anchors | 399 |
| Successful calls | 399 (100%) |
| Failed calls | 0 |
| **Positive** | **94 (23.6%)** |
| Negative | 305 (76.4%) |
| **Abstain** | **0 (0.0%)** |
| Mean runtime | 11.2s/call |
| Parse errors | 0 |

### Event Types
- vehicle: 67
- pedestrian: 13
- cyclist: 13
- motorcycle: 1

### Completeness
- 100% complete_event_visible = true
- 0% truncation
- 100% of positives have event_start/event_end boundaries

### Event Stitching
- 94 positive anchors → 51 stitched events
- Mean event duration: 5.2s
- 28 single-anchor events, 23 multi-anchor merged events
- Total event time: 267s (6.7% of video)

## 4. Output Files

- `tables/center10_full_oracle_labels.csv` (399 rows)
- `tables/center10_vlm_oracle_events.csv` (51 events)
- `tables/center10_event_stitching_trace.csv`
- `raw_vlm_responses/` (399 JSON files)

## 5. Gate Decision

```
V13_8_DECISION: FULL_CENTER10_ORACLE_REFERENCE_READY
```

All criteria met: ≥390 successful calls (399), ≤9 failed (0), abstain_rate ≤0.10 (0%), event_count ≥5 (51).
