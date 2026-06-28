# V13.10 Summary — Oracle Upper Bound, Efficiency Audit, Adaptive Search

**Date:** 2026-06-23
**Type:** EXPLORATORY (V12.1 Section 28), not certificate
**Full report:** `test_vlm/outputs/v13_10/reports/V13_10_REPORT.md`

## Key Findings

### A-1: Event-Uniqueness
Every positive anchor belongs to exactly 1 stitched event → simple OracleBest formula.

### A-2: Oracle Upper Bound
| B | OracleBest |
|---|---|
| 5 | 0.098 (5/51) |
| 10 | 0.196 (10/51) |
| 20 | 0.392 (20/51) |
| 40 | 0.784 (40/51) |
| 80 | 1.000 |

### A-3: Static Methods Far Below Upper Bound
Best efficiency at B=20: **0.350** (only 35% of optimal). 11 stalled rows where methods spent budget without finding new events.

### Part B: Adaptive Does Not Beat Static
Adaptive methods underperform at every budget. Proxy scores are too weakly correlated with events for adaptive mechanisms to add value.

## Why
- YOLO vehicle counts correlate with traffic density, not ego-path conflict
- Adaptive boost/expansion amplifies noise in high-vehicle-count regions
- Budget is dominated by false positives in proxy-top regions

## 93→18 Mismatches (Root Cause Found)
- **93 of 93 were false positives**: compared `event_recall_iou_0p3` (always 0.0) not `event_recall_overlap`
- **18 random remain**: single seed vs 50-seed mean — expected statistical noise
- **0 deterministic mismatches**: all 75 (method, budget) pairs now match
- **V13.9 overlap definition = V13.10 stitch definition** on this dataset
- See `reports/V13_10_MISMATCH_ROOT_CAUSE.md`

## Bug Fix Confirmed
After correcting field comparison + random aggregation, re-run confirms:
1. Static-vs-adaptive delta unchanged — adaptive never beats static
2. No code error in either V13.9 or V13.10 event-hit logic
3. Root cause: proxy scores too weak for spatial locality to help

## Decisions
```
V13_10A_DECISION: STATIC_METHODS_FAR_BELOW_UPPER_BOUND
ADAPTIVE_SIMULATION_DECISION: ADAPTIVE_NO_BETTER
MISMATCH_ROOT_CAUSE: V13_10_COMPARISON_BUG_NOT_SEMANTIC_DIFFERENCE
```
