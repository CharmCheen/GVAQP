# Accelerated Event Query Report V1

Current status: `IN_PROGRESS — PRE-ORACLE AUDIT`

## Strongest supported conclusion

The previous binary-SMDP stop remains valid for its old two-video, ego-path-entry task, but it neither proves nor disproves dynamic event querying for the new driver-response query. The new experiment cannot reuse those semantic labels. Three hash-bound videos and a compatible 1,475-unit grid are available; the decision-critical evidence now missing is stable new-query 32B labeling and the resulting YOLO+K3 event-recall ceiling.

## Observed evidence

- Current branch ancestry contains the complete binary-SMDP negative/insufficient evidence; no prior result was deleted or overwritten.
- Dali, Hangzhou, and Wuhan decode under ffprobe and have frozen SHA-256 identities.
- Local Qwen3-VL-32B-FP8 previously required two A100s after BF16 dequantization. Four measured inference calls took 23.609–27.116 seconds, and the model produced at least one qualitatively unsupported positive in the prior probe. It must be treated as fallible.
- All 19 current local model files, including all seven checkpoint shards (34 GB total), were directly SHA-256 checked against the prior full manifest and matched.
- The complete old Dali/Wuhan oracle has 914 ten-second units but asks about ego-path entry. The new response-required query is broader/different, so label reuse would be semantic leakage.
- A tested event-level kernel now distinguishes probable from verified events, updates K3 incrementally, enforces negative barriers and duration caps, rejects post-deadline mutations, and uses one-to-one event matching. Eighteen targeted tests pass.

## Derived implications

At the observed 24.7-second mean inference, a sequential 1,475-unit 32B pass is approximately 10.1 inference-hours before decode/preprocess overhead. Three two-GPU replicas would reduce ideal inference wall time to about 3.4 hours, but this is an estimate, not an execution record. The preregistered 30-call cross-video stability/parse/frame-sampling preflight has higher information value than immediately launching the complete oracle.

## Competing hypotheses

1. The new operational prompt is stable enough to define reference events; then the next bottleneck is YOLO+K3 event coverage.
2. The 32B labels are materially unstable or unsupported for response-required semantics; then a full grid would create expensive but weak evidence and the correct decision is `INSUFFICIENT_EVIDENCE` or an oracle-protocol revision, not controller work.
3. The oracle is adequate, but the existing person/vehicle proxy cannot recover braking events caused by traffic controls, road conditions, or lead-vehicle dynamics; this predicts a low SCAN event-recall ceiling and `REVISE_SCAN`.

## Unresolved required answers

All twelve final report questions remain open. In particular, no new-query operational references, formal scan ceiling, probable-event calibration, safe dynamic headroom, public-state model, learned controller, or ablation matrix has yet been run.
