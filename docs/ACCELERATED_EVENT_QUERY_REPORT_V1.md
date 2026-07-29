# Accelerated Event Query Report V1

Current status: `IN_PROGRESS — V1 PREFLIGHT REJECTED; V2 PROTOCOL REVISION IN PROGRESS`

## Strongest supported conclusion

The previous binary-SMDP stop remains valid for its old two-video, ego-path-entry task, but it neither proves nor disproves dynamic event querying for the new driver-response query. The new experiment cannot reuse those semantic labels. Three hash-bound videos and a compatible 1,475-unit grid are available; the decision-critical evidence now missing is stable new-query 32B labeling and the resulting YOLO+K3 event-recall ceiling.

## Observed evidence

- Current branch ancestry contains the complete binary-SMDP negative/insufficient evidence; no prior result was deleted or overwritten.
- Dali, Hangzhou, and Wuhan decode under ffprobe and have frozen SHA-256 identities.
- Local Qwen3-VL-32B-FP8 previously required two A100s after BF16 dequantization. Four measured inference calls took 23.609–27.116 seconds, and the model produced at least one qualitatively unsupported positive in the prior probe. It must be treated as fallible.
- All 19 current local model files, including all seven checkpoint shards (34 GB total), were directly SHA-256 checked against the prior full manifest and matched.
- The complete old Dali/Wuhan oracle has 914 ten-second units but asks about ego-path entry. The new response-required query is broader/different, so label reuse would be semantic leakage.
- A tested event-level kernel now distinguishes probable from verified events, updates K3 incrementally, enforces negative barriers and duration caps, rejects post-deadline mutations, and uses one-to-one event matching.
- Before any new-query 32B output existed, deterministic 2 fps contact sheets were generated for all twelve preflight clips and hash-bound to a blinded adversarial review. The review records four qualitative positives, five negatives, and three unknowns. These judgments are screening evidence, not independent human ground truth.
- The previously qualitative “no systematic unsupported positives” gate is now operationalized before outcomes: a contradiction requires two stable high-confidence 2 fps oracle positives against a medium/high frozen `not_relevant` review; one candidate requires adjudication, while two across two videos fail the gate. Review `unknown` never counts as negative.
- Twenty-one targeted tests pass, including fail-closed tests of the visual-contradiction classifier.

## Derived implications

At the observed 24.7-second mean inference, a sequential 1,475-unit 32B pass is approximately 10.1 inference-hours before decode/preprocess overhead. Three two-GPU replicas would reduce ideal inference wall time to about 3.4 hours, but this is an estimate, not an execution record. The preregistered 30-call cross-video stability/parse/frame-sampling preflight has higher information value than immediately launching the complete oracle.

Independent pre-outcome review rejected the V1 preflight as an execution gate. The contact sheets omitted the endpoint frame supplied to the model; nominal 4 fps extraction was actually about 4.286 fps; malformed label-conditional outputs could parse successfully; raw inputs were not authenticated; and degenerate all-unknown or single-class outputs could pass. Zero of 30 V1 physical calls were made, so no outcome was overwritten.

V2 now freezes an exact endpoint-inclusive target grid (21 frames at 2 fps and 41 at 4 fps), per-frame RGB identities, strict whole-string/label-conditional parsing, two pre-outcome reviews, bidirectional semantic screening, usable-class-support gates, and a 32-call design with one cross-replica anchor. The two reviewers agreed on 10 of 12 clips; the two disagreements are retained as `unknown`. An authenticated runner and analyzer are implemented: CPU validation resolves all 32 exact inputs, and synthetic attacks confirm that single-class collapse and raw/frame tampering cannot pass. Independent implementation review remains required before compute approval.

## Competing hypotheses

1. The new operational prompt is stable enough to define reference events; then the next bottleneck is YOLO+K3 event coverage.
2. The 32B labels are materially unstable or unsupported for response-required semantics; then a full grid would create expensive but weak evidence and the correct decision is `INSUFFICIENT_EVIDENCE` or an oracle-protocol revision, not controller work.
3. The oracle is adequate, but the existing person/vehicle proxy cannot recover braking events caused by traffic controls, road conditions, or lead-vehicle dynamics; this predicts a low SCAN event-recall ceiling and `REVISE_SCAN`.

## Unresolved required answers

All twelve final report questions remain open. In particular, no new-query operational references, formal scan ceiling, probable-event calibration, safe dynamic headroom, public-state model, learned controller, or ablation matrix has yet been run.
