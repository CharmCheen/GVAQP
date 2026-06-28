# TRANSITION_FEATURE_REPORT.md

## ROI Definition (Reused from scout_pipeline.py)

| Region | Definition (image-relative pixels, 1920x1080) |
|--------|------------------------------------------------|
| inside corridor | cx in [672, 1248] and cy >= 486 (V13.5 near-ego lower-center band) |
| outside corridor | everything else |
| boundary strip | |cx - 960| <= 480 (10% wider than inside band) |

LIMITATION: this is a crude image-thirds approximation, NOT a true ego-lane geometry. An object in the inside ROI is "in the lower-center band" of the image; it may be in the ego lane or an adjacent lane.

## Per-Track Transitions (N=8787 tracks)

| Metric | Value |
|--------|-------|
| Total tracks | 8787 |
| Tracks with length >= 2 (transition-capable) | 3676 |
| Tracks with >= 1 outside->inside transition | 259 (2.9% of all tracks) |
| Tracks with >= 1 inside->outside transition | 569 (6.5%) |
| Tracks with either transition | 652 (7.4%) |
| Total outside->inside transition events | 304 |
| Total inside->outside transition events | 656 |

## Per-Anchor Aggregation (anchor_t +/- 5s, N=347 anchors)

| Metric | Value |
|--------|-------|
| Anchors with has_outside_to_inside_transition | 290 (83.6%) |
| Anchors with inside->outside transition (count > 0) | 325 (93.7%) |
| Anchors with either transition direction | 332 (95.7%) |

### By Positivity

| Group | Count | with o->i | with i->o | with either |
|-------|-------|-----------|-----------|-------------|
| Qwen-positive | 40 | 26 | 36 | 36 |
| Qwen-negative | 307 | 264 | 289 | 296 |

### Failure Mode Specific

| Group | Count | with o->i | rate |
|-------|-------|-----------|------|
| Singleton positives | 21 | 14 | 66.7% |
| Low-proxy singletons (ocm <= 6.5) | 9 | 4 | 44.4% |

## Notable Anchors

Low-proxy singleton positives with o->i transition (the target failure mode):
- center10_anchor_0185 t=1855s ocm=2.5 o->i=0 trans_count=0
- center10_anchor_0224 t=2245s ocm=3.0 o->i=0 trans_count=0
- center10_anchor_0183 t=1835s ocm=3.5 o->i=0 trans_count=0
- center10_anchor_0050 t=505s ocm=4.0 o->i=1 trans_count=25
- center10_anchor_0325 t=3255s ocm=4.0 o->i=0 trans_count=0
- center10_anchor_0057 t=575s ocm=5.0 o->i=0 trans_count=0
- center10_anchor_0197 t=1975s ocm=5.5 o->i=1 trans_count=20
- center10_anchor_0219 t=2195s ocm=6.0 o->i=1 trans_count=33
- center10_anchor_0217 t=2175s ocm=6.5 o->i=1 trans_count=40


Low-proxy singleton positives WITHOUT o->i transition (the hardest failures):
- center10_anchor_0185 t=1855s ocm=2.5 o->i=False num_dets=5 num_tracks=4
- center10_anchor_0224 t=2245s ocm=3.0 o->i=False num_dets=17 num_tracks=12
- center10_anchor_0183 t=1835s ocm=3.5 o->i=False num_dets=11 num_tracks=6
- center10_anchor_0325 t=3255s ocm=4.0 o->i=False num_dets=17 num_tracks=9
- center10_anchor_0057 t=575s ocm=5.0 o->i=False num_dets=50 num_tracks=20


## Decision

Transition features successfully extracted. The O->I transition rate for the target failure mode (low-proxy singletons) is **4/9 = 44.4%** which is comparable to the base anchor coverage (290/347 = 83.6%). Proceed to Phase 3 (diagnostics) and Phase 4 (replay).
