# SCAN Innovation Hypothesis Registry

All event claims are relative to the frozen full-context Oracle pseudo-reference.
Hypotheses are registered before their result metrics are computed.

## YGS-H000 — Layer-0 baseline reconstruction

```text
hypothesis_id = YGS-H000
motivation = Establish the per-video strongest causal coverage comparator.
single_changed_mechanism = NONE; evidence reconstruction only.
legal_inputs = frozen replay traces, public policy state, evaluator-only exposure after runs.
expected_effect = Reproduce prior per-video coverage winners and offline upper bound.
baseline = Sequential, Random, Uniform-prefix, Anytime Largest-Gap, Macro Largest-Gap, M8 safe.
primary_metric = Event-Exposure–SCAN-Time AUC at matched wall-clock.
acceptance_gate = hashes and recomputed values agree with authoritative audit.
rejection_gate = asset/hash/metric disagreement.
implementation_hash = recorded in outputs/scan_innovation_agentic_loop_v1/hypotheses/YGS-H000.json
result = ACCEPTED. Full-horizon winners: short Anytime Largest-Gap (0.529643), long Macro Largest-Gap (0.528238). Replay-60 winners: short Sequential (0.132097), long Macro Largest-Gap (0.050177). Physical-60 winners among tested policies: short Sequential (0.132716), long Uniform-prefix (0.049693); Macro Largest-Gap lacks a physical run. M8 is weaker on both videos.
decision = Freeze comparator per video and per horizon; do not claim one universal coverage winner.
next_allowed_branch = YGS-H001 if accepted.
```

## YGS-H001 — Frozen global Q1-L semantic preview

```text
hypothesis_id = YGS-H001
motivation = Prior P1-L is the only semantic preview with stable AUC and positive medium-budget net yield.
single_changed_mechanism = Add frozen 0.2-FPS YOLOv8n detection-only full-timeline preview to coverage.
legal_inputs = source video, low-rate YOLO detections, public region boundaries.
expected_effect = Preserve prior nested Recall/AUC and cost below 10% full SCAN.
baseline = frozen P0 and causal coverage.
primary_metric = nested Recall@20 and preview/full-SCAN cost ratio.
acceptance_gate = deterministic, nonleaky, cost <=10%, reproduction within numerical tolerance.
rejection_gate = determinism/leakage/cost failure.
implementation_hash = f6c6e030ff3405168ca18026c809c8ab36e96459b1ad50746ef7af1e1d7dca61
result = ACCEPTED as a sensing primitive: byte-deterministic across two runs, legal input boundary, cost ratio 0.032730, exact reproduced Recall@20 0.328571/0.321244 and AUC 0.593571/0.612979. Static scheduling Gate remains failed only on Recall@20.
decision = Retain Q1-L as the frozen global preview; do not admit scheduler; proceed to the preregistered selective escalation test.
next_allowed_branch = YGS-H002 if accepted.
```

## YGS-H002 — Uncertainty-driven selective high-rate YOLO escalation

```text
hypothesis_id = YGS-H002
motivation = P1-L passes 9/10 prior gates but misses Recall@20; ambiguity near the allocation boundary may be reducible with selective higher-rate detections.
single_changed_mechanism = For a capped subset chosen only by Q1 model uncertainty/boundary proximity, add 2-FPS 320px YOLO detection preview.
legal_inputs = frozen Q1 features, train-fold model uncertainty, source-video frames in selected regions, actual preview costs.
expected_effect = Raise nested Recall@20 to >=0.40 on both videos while total preview cost remains <=10%.
baseline = P1-L static-only nested ranker and each video's strongest causal coverage.
primary_metric = nested Recall@20%-Region-Cost.
acceptance_gate = full Layer-1 Static Observability Gate in the frozen contract.
rejection_gate = any Layer-1 Gate failure, leakage, cost >10%, or one-video-only improvement.
implementation_hash = recorded in outputs/scan_innovation_agentic_loop_v1/hypotheses/YGS-H002.json
result = REJECTED. Combined preview cost ratio 0.052925 passed. Recall@20 was 0.328571/0.316062 and AUC 0.593571/0.609145. It did not strictly beat Q1-L on either video, failed Recall>=0.40 on both, degraded long-video leave-best robustness, and failed common positive/net-yield requirements.
decision = Q2 high-rate detection does not resolve Q1 ambiguity; scheduler remains prohibited.
next_allowed_branch = one materially different registered Q3 directional-motion escalation.
```

Frozen H002 details are stored before preview execution in
`outputs/scan_innovation_agentic_loop_v1/contracts/YGS-H002.json`. The
escalation subset is the nearest regions on both sides of the Q1-L 20%-cost
allocation boundary, tie-broken by probability closeness to 0.5, capped at
10% of each video's duration. It is not selected by event labels or by simply
taking the highest Q1 scores.

## YGS-H003 — Uncertainty-selected directional motion escalation

```text
hypothesis_id = YGS-H003
motivation = H002 shows detection sampling rate is not the bottleneck; strict cut-in value may require directional motion evidence absent from detection-only Q1.
single_changed_mechanism = Replace Q2 high-rate detections with selected-region 5-FPS 320x180 directional optical-flow/frame-difference preview.
legal_inputs = frozen Q1 boundary/uncertainty selection, source-video frames in selected regions, actual preview costs.
expected_effect = Lateral/expansion/center-flow summaries improve residual event ranking on both videos.
baseline = P1-L static-only nested ranker and each video's strongest causal coverage.
primary_metric = nested Recall@20%-Region-Cost.
acceptance_gate = full Layer-1 Static Observability Gate in the frozen contract.
rejection_gate = any Layer-1 Gate failure, leakage, cost >10%, or one-video-only improvement.
implementation_hash = 602259ac80c7c18a0c1406b84ec29761ba846faba4f7e08ad97e24b1d1bccbe1 (preview); evaluator hash recorded in YGS-H003.json.
result = REJECTED. Combined cost ratio 0.070582 passed. Recall@20 was 0.328571/0.326425 and AUC 0.593571/0.614326. Short video did not improve over Q1-L; both Recall values missed 0.40; cost-adjusted primary net yield failed.
decision = Directional motion is insufficient and video-unstable; scheduler prohibited; freeze safe coverage package.
next_allowed_branch = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST.
```
