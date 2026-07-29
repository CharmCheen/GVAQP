# Hypothesis Registry

## H1 — Operational-oracle adequacy

Status: `ACTIVE — V1 FALSIFIED; V2 SEALED AND INDEPENDENTLY CLEARED FOR APPROVAL REQUEST`

- Why important: every formal reference and downstream conclusion depends on the 32B response-required label being parseable and sufficiently stable.
- Expected observation under H1: authenticated identical inputs are exactly reproducible within and across replicas; strict parse success is complete; both decided classes have cross-video support; unknowns do not collapse the sample; exact 2/4 fps inputs do not cause unresolved polarity/boundary/response instability; post-output review finds no systematic unsupported or missed claims.
- Main counter-hypothesis: response necessity cannot be inferred reliably from sparse visual frames, and the prior unsupported Hangzhou positive generalizes to this prompt.
- Pass standard: all V2 authentication and strict-parse gates pass; 12/12 same-process pairs and the cross-replica anchor are byte-reproducible; class-support/unknown gates pass; no sampling polarity failure; every semantic disagreement and model-positive cause claim is adjudicated under the frozen rules.
- Fail standard: any artifact/identity failure, parse failure, reproducibility failure, class collapse, unresolved sensitivity transition, systematic bidirectional semantic contradiction, or unsupported cause pattern.
- Minimal experiment: the targeted 32-call V2 pilot. A pass supports only a larger content-blind representative audit, not the full oracle.

## H2 — YOLO/K3 event-recall ceiling is adequate

Status: `ACTIVE — BLOCKED BY H1/FULL ORACLE`

- Why important: no SCAN/VERIFY controller can recover operational events that never enter the candidate-to-event pipeline.
- Expected observation under H2: unlimited VERIFY over all frozen YOLO candidates materializes most operational reference events on each video, with misses not dominated by a whole causal class.
- Main counter-hypothesis: traffic-control, lead-vehicle dynamics, and road-condition events lack person/vehicle proxy signatures, producing a low or highly video-dependent ceiling.
- Pass standard: preregister after H1 and before ceiling evaluation; provisional mechanism target is event recall ceiling at least 0.80 on every video at the frozen one-to-one matcher.
- Fail standard: any video falls below the frozen target or a major event class is structurally absent; route to `REVISE_SCAN`.
- Minimal experiment: full frozen YOLO scan joined to full operational oracle grid, then K3 materialization with unlimited verification.

## H3 — Event-calibration VERIFY exposes binary switching headroom

Status: `ACTIVE — DEFERRED UNTIL H2 AND COST SAFETY PASS`

- Why important: previous `VERIFY_TOP1` evidence contained one SCAN-better state, no VERIFY-better state, and unsafe/incomplete cost support; event-level calibration may reveal verification value that top-candidate confirmation misses.
- Expected observation under H3: both stable SCAN-better and VERIFY-better states occur on multiple videos, and the safe dynamic oracle exceeds the best fixed/two-stage policy without precision or deadline violations.
- Main counter-hypothesis: most states are effectively tied, or gains are timing artifacts/precision violations rather than event-set calibration.
- Pass standard: all six dynamic-headroom gates in the V1 contract pass at beam widths 128/512/2048.
- Fail standard: cross-video action diversity or safe-oracle improvement fails; choose the corresponding terminal/revision decision without training a complex controller.
- Minimal experiment: label-hiding replay with deterministic `VERIFY_EVENT_CALIBRATION_TARGET`, fixed behavior policies, and conditioned branch search.
