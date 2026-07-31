# SCAN policy

`ANYTIME_LARGEST_GAP` is the selected safe coverage policy. It is public-state-only, deterministic, complete without replacement, and independent of `video_id`. It provides anytime geometric coverage rather than a claim that geometric distance predicts event value.

`SEQUENTIAL`, `UNIFORM_PREFIX`, and `MACRO_REGION_LARGEST_GAP` are marked `EVALUATION_BASELINE`. Their presence does not authorize automatic selection of historical per-video winners. YOLO-guided scheduling is closed under the tested signals and is absent from runtime code.
