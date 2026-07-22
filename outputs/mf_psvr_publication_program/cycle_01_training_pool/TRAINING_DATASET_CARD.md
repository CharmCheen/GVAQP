# MF-PSVR provider-separated training-pool dataset card

## Current status

`AUDIT_READY_ORACLE_NOT_RUN`. This is a source and protocol freeze, not a labeled dataset and not a
Cycle-1 completion claim. No YOLO, tracking, frozen-oracle, model-training, V0/V1 semantic-label, or
paper-held-out access occurred in this stage.

## Objective

Test whether provider-separated driving clips with unresolved capture-session lineage contain enough
frozen-query support to train and validate
the MF-PSVR L1 refiner, especially where raw detector scores fail. The decision-critical uncertainty
is Q2 support; Nexar's collision tag is not semantically equivalent to either frozen query.

## Observed composition

- Nexar: 603 exact local provider video clips, 6.293 video hours,
  2654 nominal 10-second units, and 10149212830 bytes.
- Nexar weak sampling tags: 200 collision/near-collision and
  403 normal-driving videos. These are **not** Q1/Q2 labels.
- Frozen session roles: {"model_calibration": 102, "model_train": 413, "pool_audit": 88}.
- DrivingDojo-mini: 32 image-sequence sessions, all license-quarantined.
- Frozen-oracle labels: 0. Q1 positives: unknown. Q2 positives: unknown.

## Identity and independence

Every eligible Nexar MP4 is SHA-256 hashed and matched to its Hugging Face LFS object identity at
repository revision `aa97deda5a59f00bb7187739053b7c72e14374df`. The manifest's `session_id` field is currently a provider
video-ID proxy because the released metadata contains no trip/capture-session lineage. Exact overlap with
V0/V1 is zero, and no V0/V1 slice, re-encode, or derivative was intentionally selected. Cross-provider
separation is established, but perceptual equivalence and shared capture-session lineage remain
unresolved; this is not reported as proven statistical independence.

The `pool_audit` role is an internal independent-pool slice. It is not the unopened paper held-out
split. Splits are deterministic at provider-video level and independent of weak tags and oracle
outcomes. Leave-one-source-video-out is supported; a stronger leave-one-capture-session-out claim is
not supported until trip lineage is available.

## Labels and supervision scope

The authoritative oracle emits one generic unit label and `involved_object` for a center-anchored
10-second unit. The frozen final-tail rule uses the last 5 seconds when the nominal final anchor is
past the media end, so that unit may overlap its predecessor.
Q1 is projected from `vehicle|cyclist`; Q2 from `pedestrian|cyclist`; free-text evidence is never used
for projection. A track is only the causal scheduling witness. No track is oracle-confirmed.

Consequently, supervised data use one row per `(source, session, query, unit)` verification key.
Duplicating a unit label over every track is prohibited. If track-level rows are studied, they require
either a witness frozen before the label or an explicitly reported multiple-instance objective.

## Acquisition design

The frozen candidate pipeline is the label-independent pool Y8 configuration: YOLOv8n at 640, 5 fps, confidence
0.25, NMS IoU 0.45, and frozen ByteTrack parameters, with fresh tracker state per 10-second unit.
Y8 is selected here because it is the only preregistered local detector with nonempty ontology support
for both Q1 and Q2; the V0/V1 outcome-selected final-proxy artifact is not an input.
The initial 96-call support pilot is frozen across query-score, weak-tag, hard-case, and random strata
before its first oracle call. One generic call supplies both deterministic query projections.

The support-existence gate requires 8 positive units across 5 videos per query. Separate frozen
train/calibration/pool-audit positive and negative gates determine actual usability; calibration and
audit failures cannot be adaptively replaced. A later model-train-only top-up is capped at 320 total
calls and is permitted only after the pilot decision. Enriched positive fractions are not prevalence estimates.

## Cost estimate before authority

- Full-pool Y8 extraction: 122,694 exact planned frames imply about
  17.0 detector GPU-minutes; the frame-p95
  wall estimate plus initialization and the direct short-clip overhead profile is
  47.1 minutes.
- Stage-A 96-call oracle pilot: p95 sequential reservation about
  1.01 hours including one model initialization.
- Full 320-call cap: p95 sequential reservation about
  3.32 hours including initialization.

No such compute was launched by this audit.

## Known biases and exclusions

- The usable pool currently has one provider dataset and many exact-unique provider videos, but no
  released trip/capture-session grouping; within-provider session leakage cannot yet be ruled out.
- Only 200 local Nexar collision-tagged videos are present versus 403 normal-tagged videos; this is a
  convenience subset, not a representative prevalence sample.
- Collision and alert-time metadata are only weak sampling aids and are unreliable for ego-path entry.
- The prior 5-second Nexar Qwen audit used a different prompt/sampling contract and is excluded from
  labels and exact unit selection.
- DrivingDojo-mini could plausibly enrich Q2, but license uncertainty currently blocks its use.
- Container metadata was probed; a complete decode of every frame was not performed in this stage.

## Falsifiable next decision

Run the frozen Y8 extraction and the 96-call support pilot only after compute/oracle authority. Reject
the Nexar-only training-pool hypothesis if either query fails the preregistered support gate. In that
case the next action is to acquire a directly licensed Q2-enriched independent source, not to retune
the frozen oracle or reinterpret weak tags.
