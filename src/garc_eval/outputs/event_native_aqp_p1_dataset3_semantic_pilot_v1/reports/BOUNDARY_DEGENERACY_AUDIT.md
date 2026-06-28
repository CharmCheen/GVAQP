# Boundary Degeneracy Audit — dataset3 P1 Pilot

**Finding:** All 5 positive anchors output identical event boundaries (start=0.0s, end=0.7s). This is templated, not real temporal localization.

---

## Evidence

| anchor | event_start | event_end | boundary_status | complete_event_visible |
|---|---|---|---|---|
| 0060 | 0.0 | 0.7 | ok | True |
| 0195 | 0.0 | 0.7 | ok | True |
| 0197 | 0.0 | 0.7 | ok | True |
| 0247 | 0.0 | 0.7 | ok | True |
| 0325 | 0.0 | 0.7 | ok | True |

- `event_start`: 1 unique value / 5 positives
- `event_end`: 1 unique value / 5 positives
- `boundary_status`: all "ok"
- `complete_event_visible`: all True

## Why This Is Degenerate

1. A pedestrian crossing and a bus lane-change do not both occur in exactly 0.0–0.7s.
2. All events starting at 0.0s (clip beginning) is implausible — events should be distributed within the 10s window.
3. The VLM reports `boundary_status=ok` and `complete_event_visible=True` for all, but the uniform values contradict this — if boundaries were real, they would vary.
4. On realcartest V13.8 (same VLM, same prompt), event boundaries varied (1s–40s+). The template on dataset3 is a format/processing issue, not a fundamental VLM limitation.

## Root Cause Hypothesis

The transformers warning at inference time:
```
Asked to sample `fps` frames per second but no video metadata was provided
which is required when sampling with `fps`. Defaulting to `fps=24`.
Please provide `video_metadata` for more accurate results.
```

The VLM receives 21 PIL images via `{"type": "video", "video": pil_frames, "fps": 2.0}` but **no video metadata** (duration, fps, timestamp). Without temporal metadata, the VLM cannot map frame indices to timestamps, so it outputs a fixed 0.0–0.7s boundary — likely a default/template response when temporal context is missing.

This warning appeared on realcartest V13.8 too, but realcartest had varied boundaries. The difference may be:
- realcartest: 24fps video, 10s clip = 240 frames, sampled at 2fps = 20 frames. The VLM may have inferred rough timing from frame count.
- dataset3: 30fps video, 10s clip = 300 frames, sampled at 2fps = 21 frames. Similar count, but the VLM's temporal reasoning may be more sensitive to the missing metadata on this video's content type.

**This is not conclusive — further investigation needed at P1b.**

## Impact on AQP Pipeline

| AQP stage | impact |
|---|---|
| Clip-level recall (P2 budget-quality) | **Low** — recall counts whether a positive anchor is found, not the boundary precision |
| Event stitching (merge positive anchors) | **High** — if all events are 0.7s, merge logic produces artificial uniformity; stitched event durations will all be ~0.7s |
| Boundary refinement (P1b) | **Blocking** — cannot refine boundaries that are already templated |
| Certificate (clip-level recall guarantee) | **Low** — the certificate is on clip recall, not boundary precision |

## Recommended Fixes (priority order)

### Fix 1: Pass video_metadata to processor (most likely root cause)
```python
from transformers import AutoProcessor
# add video_metadata to the message
messages = [{"role": "user", "content": [
    {"type": "video", "video": pil_frames, "fps": 2.0,
     "video_metadata": {"duration": clip_duration, "fps": 2.0}}
]}]
```
This gives the VLM temporal context to produce real boundaries. **Test this first at P1b with 5-10 anchors.**

### Fix 2: Use contact-sheet format with explicit frame timestamps
V13.6 tested `contact_sheet_10s_5frames` — uniformly spaced 5 frames from [center_t-5, center_t+5] via `np.linspace`. If frames have explicit timestamps embedded (or the prompt mentions them), the VLM may localize better.

### Fix 3: Post-hoc boundary refinement query
For each positive anchor, run a second VLM query:
> "The following clip contains an ego-path intrusion event. Localize the event start and end in seconds. The clip is 10 seconds long. Frames are sampled at 2fps."

This forces the VLM to produce specific boundaries rather than a template.

### Fix 4: Accept for P2, document limitation
If fixes 1–3 fail, accept the 0.7s boundary for P2 budget-quality experiments. Clip-level recall does not depend on boundary precision. Document this as a known limitation. Stitched event count may be inaccurate, but the budget-decomposition AQP contribution (set-cover, diversity-prefilter) operates on anchor-level labels, not event boundaries.

## Verification Plan for P1b

At P1b (full 347-anchor scan), run the first 10 anchors with Fix 1 (video_metadata). Check:
- Are `event_start` / `event_end` values varied (not all 0.0/0.7)?
- Is `boundary_status` distribution non-uniform (some truncated, some uncertain)?
- Does the transformers warning disappear?

If yes → proceed with full scan using Fix 1. If no → try Fix 2 or Fix 3 on the next 10. If all fail → use Fix 4 and proceed.

## Comparison to realcartest V13.8

| | realcartest V13.8 | dataset3 P1 |
|---|---|---|
| event_start values | varied (0.0–9.0+) | all 0.0 |
| event_end values | varied (1.0–10.0) | all 0.7 |
| boundary_status | ok, truncated_start, truncated_end, uncertain | all ok |
| transformers warning | present | present |
| video fps | 24 | 30 |

The same warning on both videos but different boundary behavior suggests the warning is necessary but not sufficient to explain the degeneracy. The video content type (Chinese urban crosswalk-heavy vs realcartest's vehicle-centric) may also play a role — the VLM may be more confident localizing vehicle maneuvers (which have clear lane-change trajectories) than pedestrian crossings (which may be perceived as instantaneous).
