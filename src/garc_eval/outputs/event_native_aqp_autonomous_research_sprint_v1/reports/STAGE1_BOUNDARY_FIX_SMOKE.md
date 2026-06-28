# Stage 1: Boundary-Fix Smoke Report

**Date:** 2026-06-25
**Output:** `analysis/stage1_boundary_scheme_comparison.csv`
**Decision:** `USE_CLIP_LEVEL_LABELS_AND_POSTHOC_BOUNDARY`

---

## Test Setup

14 anchors tested: 5 P1 positives (0060, 0195, 0197, 0247, 0325) + 5 high-score negatives (0320, 0251, 0198, 0211, 0244) + 4 medium negatives (0006, 0092, 0146, 0231).

3 schemes compared:
- **Scheme A**: Video frames at fps=2 with `raw_fps=30` metadata fix
- **Scheme B**: Timestamped contact sheet (5 frames with timestamp labels, image input)
- **Scheme C**: Post-hoc boundary localization query (positives only, explicit boundary prompt)

---

## Results

| metric | Scheme A (video) | Scheme B (contact sheet) | Scheme C (post-hoc) |
|---|---|---|---|
| completed | 14/14 | 14/14 | 3/5 (timeout) |
| parse success | 14/14 | 14/14 | 2/3 |
| positives found | 4 | 4 | N/A (boundary-only) |
| negatives found | 10 | 10 | N/A |
| label match vs P1 | **13/14 (93%)** | 11/14 (79%) | N/A |
| unique event_start | **1 (all 0.0)** | 4 (varied) | 2 (varied) |
| unique event_end | **1 (all 0.7)** | 4 (varied) | 2 (varied) |
| boundary degenerate? | **YES** | NO | NO |
| runtime/anchor | ~12s | ~10s | ~15s |

### Scheme A mismatches:
- `0197`: P1=positive → A=negative (bus cut-in — borderline case, VLM may be inconsistent on vehicle merge events)

### Scheme B mismatches:
- `0060`: P1=positive → B=negative (**missed positive** — pedestrian crossing not visible in 5 frames)
- `0197`: P1=positive → B=negative (same as Scheme A)
- `0231`: P1=negative → B=positive (**false positive** — VLM sees event in contact sheet that isn't there)

### Scheme C partial results:
- `0060`: parse error (empty response)
- `0195`: event_start=0.0, event_end=0.5 (varied from 0.7 template)
- `0197`: event_start=0.5, event_end=1.0 (varied from 0.7 template)

---

## Analysis

### 1. Boundary degeneracy is NOT caused by missing video metadata

Scheme A passed `raw_fps=30` to the VLM but still produced 0.0-0.7 boundaries for all positives. The transformers warning persists ("no video metadata was provided"). The `raw_fps` parameter in `fetch_video` creates fake metadata but does not solve the temporal localization issue. **The boundary template is a VLM behavior, not a metadata issue.**

### 2. Contact sheets produce varied boundaries but degrade label quality

Scheme B (contact sheet) produces 4 unique event_start and 4 unique event_end values — boundaries are varied. However, this comes at a cost:
- Misses positive 0060 (pedestrian crossing visible in video but not in 5-frame sample)
- Adds false positive 0231 (VLM interprets contact sheet frames as showing an event)
- The boundaries are in absolute time (1952.5s), not relative to clip start as the prompt requests

This means contact sheets trade label quality for boundary variety — **not acceptable for the AQP contribution which requires reliable clip-level labels.**

### 3. Post-hoc boundary localization shows promise but is incomplete

Scheme C produced varied boundaries (0.0-0.5, 0.5-1.0) on the 2 completed positives. The post-hoc query format (explicit boundary localization with before/during/after evidence) may produce better boundaries than the combined label+boundary query. But it requires a separate VLM call per positive and was incomplete due to timeout.

### 4. Label stability is the critical metric for AQP

For the AQP contribution (clip-level recall under budget), label stability is more important than boundary precision:
- Scheme A: 93% label match → reliable for clip-level labels
- Scheme B: 79% label match → unreliable, would bias the AQP evaluation
- The boundary template (0.0-0.7) does NOT affect clip-level recall — it only affects event stitching

---

## Decision: `USE_CLIP_LEVEL_LABELS_AND_POSTHOC_BOUNDARY`

For the full 347-anchor scan (Stage 2):
1. **Use Scheme A** (video frames at fps=2, same V13.6 prompt, same V13.8 approach) — best label stability
2. **Accept templated boundaries** (0.0-0.7) as a known limitation — document in all reports
3. **Use Scheme C (post-hoc) for boundary refinement** on positives after the full scan — separate step, not blocking
4. **Clip-level labels are the primary output** — the AQP contribution operates on positive/negative anchor labels, not boundaries
5. **Event stitching will use anchor-level labels** — adjacent positive anchors are merged into event clusters without relying on boundary precision

### Why not Scheme B for the full scan?
- 79% label match would introduce systematic bias (misses some positives, adds false positives)
- The false positive on 0231 shows the VLM interprets contact sheets differently than video
- 5 frames cannot capture the temporal dynamics needed for ego-path intrusion detection

### Why not fix boundaries before the full scan?
- The AQP contribution is clip-level recall, not boundary precision
- Full scan labels are needed first to enable budget replay (Stage 5)
- Boundary refinement is a post-hoc step that can be done on positives after the full scan
- Delaying the full scan for boundary fixes would block all downstream analysis
