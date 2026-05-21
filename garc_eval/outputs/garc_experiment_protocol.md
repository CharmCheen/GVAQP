# G-ARC Clip-Level Experiment Protocol

## Research Question

Does a frame-level statistical guarantee (e.g., SUPG's recall guarantee at
gamma=0.9) transfer to clip-level recall when contiguous positive frames are
merged into temporal events?

## Hypothesis

Frame-level guarantee may fail at clip level. A method that achieves 97% frame
recall could miss entire temporal clips if it selects sparse positive frames
across different clips rather than dense coverage within each clip. The
frame-to-clip recall gap is expected to increase when:
- Positive events are short relative to the frame sampling budget
- The method selects frames sparsely (e.g., SUPG-PT with low recall)
- Gap tolerance is tight (fewer frames merged)

## Dataset Requirements

A dataset suitable for clip-level evaluation must have:
1. **Temporal continuity**: Frames must come from continuous video with known
   timestamps or frame indices.
2. **Sufficient scale**: N >= 10,000 sampled frames.
3. **Positive frame rate**: 1%-30% (not degenerate all-positive or all-negative).
4. **Ground-truth clips**: Enough labeled temporal events to evaluate clip
   recall/precision meaningfully (>= 10 gt clips).
5. **Proxy/oracle pair**: A cheap proxy (e.g., YOLOv8n) and expensive oracle
   (e.g., YOLOv8x or human labels) for SUPG evaluation.

## Query

**Predicate**: `count_car(frame) >= K`

Where K is calibrated per dataset to achieve the target positive frame rate
(1%-30%). The predicate is evaluated per-frame using oracle counts.

## Metrics

### Frame-Level (existing)
- **Frame recall**: fraction of positive frames selected
- **Frame precision**: fraction of selected frames that are positive
- **Selected N/N**: fraction of total frames selected (budget efficiency)

### Clip-Level (new)
- **Clip recall**: fraction of ground-truth clips matched (IoU >= threshold)
- **Clip precision**: fraction of predicted clips matched (IoU >= threshold)
- **Mean IoU**: average best-IoU across ground-truth clips
- **GVR (Guaranteed Video Rate)**: fraction of trials where clip_recall >= threshold
- **Frame-to-clip gap**: frame_recall - clip_recall (positive = guarantee loss)

### Parameters
- **min_duration_sec**: minimum clip duration (default: 1.0s)
- **gap_tolerance_sec**: maximum gap to merge (default: 0.5s)
- **iou_threshold**: IoU threshold for matching (default: 0.5)
- **fps**: frames per second (dataset-dependent)

## Baselines

| Method | Description |
|--------|-------------|
| **Oracle-only** | Select all positive frames (upper bound) |
| **Proxy-only** | Select all frames with proxy_score >= threshold |
| **U-NOCI-RT+** | Uniform random sampling, empirical threshold, no CI |
| **U-CI-RT+** | Uniform random sampling with CI-based threshold |
| **SUPG-RT+** | SUPG with recall target (gamma=0.9) + clip evaluation |
| **SUPG-PT+** | SUPG with precision target + clip evaluation |

The "+" suffix denotes clip-level evaluation applied on top of the frame-level
selection method.

## Success Criteria

1. **Transfer holds**: SUPG-RT clip_recall >= 0.85 (given frame_recall >= 0.95)
2. **GVR >= 0.9**: In >= 90% of trials, clip_recall meets the threshold
3. **Frame-to-clip gap < 0.1**: Frame recall does not degrade by more than 10%
   when moving to clip level
4. **SUPG-RT outperforms U-NOCI-RT at clip level**: Consistent with frame-level

## Failure Criteria

1. **Transfer fails**: SUPG-RT clip_recall < 0.7 despite frame_recall >= 0.95
2. **GVR < 0.7**: Clip-level guarantee is unreliable
3. **Frame-to-clip gap > 0.2**: Significant guarantee loss at clip level
4. **No method differentiation**: All methods produce similar clip metrics

## Why BDD100K Is Not Enough

BDD100K is an image-level benchmark:
- No temporal continuity between frames (images from different driving clips)
- No meaningful clip-level events to evaluate
- Frame labels are independent, not part of temporal sequences
- Cannot compute clip IoU, clip recall, or GVR

Clip-level evaluation requires continuous video with temporal ground-truth
events. BDD100K validates the frame-level SUPG pipeline but does not address
the clip-level transfer question.

## Experiment Phases

### Phase 1: Synthetic Clip Smoke (scaffold)
- Generate synthetic frame labels with known clip structure
- Validate clip_metrics module end-to-end
- No real video data needed

### Phase 2: Real Video Smoke
- Use cached BDD100K-like data with synthetic temporal structure
- Validate the full pipeline with real proxy/oracle scores
- Single method, single dataset, 5 trials

### Phase 3: Formal Clip Experiment
- Real temporal video dataset (UA-DETRAC, CityFlow, or equivalent)
- All 6 baselines, 100 trials per method
- Full clip metrics report with GVR

---

Generated: 2026-05-21
