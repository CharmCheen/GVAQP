# Stage 6: Full-Video Call Cost Estimates

**Date:** 2026-06-23

## Policy Call Counts for realcartest.mp4 (3,987s)

| Policy | Calls | Clip Duration | Anchor Strategy |
|---|---|---|---|
| **fixed_5s_nonoverlap** (V13.5 baseline) | **798** | 5s | uniform every 5s |
| fixed_10s_sliding_stride5 | 797 | 10s | sliding window, 5s stride |
| **uniform_anchor_10s_context** | **399** | 10s | uniform every 10s |
| uniform_anchor_15s_context | 266 | 15s | uniform every 15s |
| uniform_anchor_20s_context | 200 | 20s | uniform every 20s |
| proxy_top10pct_anchor_10s | 79 | 10s | top 10% proxy fusion |
| proxy_top20pct_anchor_10s | 159 | 10s | top 20% proxy fusion |
| proxy_top30pct_anchor_10s | 239 | 10s | top 30% proxy fusion |

## Key Observations

1. **uniform_anchor_10s_context halves VLM calls** vs fixed_5s_nonoverlap (399 vs 798). The same 10s context as fixed_10s_sliding but without overlap — each anchor covers ±5s.

2. **uniform_anchor_15s_context** reduces to 266 calls (1/3 of baseline).

3. **Proxy-guided anchors** can reduce calls dramatically (79-239), but recall depends on proxy quality.

4. **fixed_10s_sliding** provides no call savings — every 5s a new 10s window is needed, same count as 5s nonoverlap.

## Questions for Sensitivity Analysis

- Does center_10s match or improve on fixed_5s for event completeness?
- Can proxy-guided anchors retain event recall?
- What is the expansion overhead when events are truncated?
