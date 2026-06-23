# V13.6 Clip Construction Sensitivity — Compact Summary

**Date:** 2026-06-23
**Full report:** `test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/reports/FINAL_REPORT.md`

---

## Objective

Evaluate whether anchor-centered clip construction and adaptive context expansion are more efficient or more event-complete than the fixed 5s non-overlapping clip grid.

## Method

- 52 base clips from V13.5 pilot (18 positives, 10 negatives, 24 abstains)
- 8 construction policies × 52 clips = **416 VLM calls** (Qwen3-VL-32B-Instruct, A800 GPU)
- New V13.6 prompt: normal driving → negative (not abstain)

## Key Result: Abstain Problem Fixed

| | V13.5 Prompt | V13.6 Prompt |
|---|---|---|
| Abstain rate | **66%** | **0%** |
| Positive rate | 18% | 44-67% |

The V13.6 "negative not abstain" rule eliminates the unusable abstain rate.

## Positive Detection by Context Length

| Policy | Positives (/52) | Rate | vs fixed_5s |
|---|---|---|---|
| fixed_5s_original | 23 | 44% | baseline |
| center_4s | 23 | 44% | 87% retention |
| center_6s | 27 | 52% | 91% retention |
| **center_10s** | **29** | **56%** | **91% retention, 6 new finds** |
| center_15s | 31 | 60% | 91% retention |
| center_20s | 27 | 52% | 78% retention |

## Call Cost at Full-Video Scale

| Policy | VLM Calls | vs baseline |
|---|---|---|
| fixed_5s_nonoverlap | 798 | 1.00× |
| **uniform_anchor_10s_context** | **399** | **0.50×** |
| uniform_anchor_15s_context | 266 | 0.33× |

## Completeness

All policies: 100% complete_event_rate, 0% truncation. Events in this video are brief and fully contained in 5-10s windows. Zero expansion calls needed.

## Decision

```
FINAL_DECISION: USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE
```

center_10s dominates fixed_5s: 26% more positives found, 91% retention, half the VLM calls, zero abstain, zero truncation, zero expansion overhead.
