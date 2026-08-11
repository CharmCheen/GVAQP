# Data availability audit

## Released and usable for exploratory replay

- Older ARC cached domains contain canonical units, one raw proxy score per
  unit, cached oracle labels, and reference events. Hash binding and the shared
  evaluator were verified by the existing replay loader.
- Older RC-SEM artifacts contain causal action traces, K3 predictions,
  event matches, and 126 cached closed-loop runs. These use abstract SCAN cost
  `0.1` and VERIFY cost `1.0`, not seconds.
- A small physical Hangzhou probe has paired 8B/32B outputs for three unique
  clips (plus one deterministic repeat per model), identical decoded inputs,
  stage timing, and memory observations.

## Missing for the frozen V3 query

The following handoff prerequisites do not exist as released artifacts:

- `unit_labels.parquet` and `authenticated_full_grid_manifest.json`;
- `k3_model_relative_event_relation.parquet`, `k3_reference_manifest.json`,
  and `k3_eventization_report.md`;
- V3 `scan_candidates.parquet`, `candidate_features.parquet`, and
  `candidate_to_reference_join.parquet`;
- `SCAN_EVENT_RECALL_CEILING.json`;
- observed complete-path SCAN/VERIFY/K3/commit costs and conservative bounds.

The main repository status files independently mark SCAN candidates,
operational reference events, cost calibration, and label-hiding replay as
`NOT_RUN`.

The attempted full-grid cannot fill these gaps: it fail-stopped at 136
completed units on a sealed per-call cost-limit breach. Partial records are
explicitly non-reference and were not opened. Under the frozen policy there is
no same-experiment retry or resume authority.

## SCAN feature audit

The cached domains preserve only the final scalar `proxy_score`. They do not
provide a V3-bound table of object classes/counts, tracks, relative motion,
ego-path interaction, lane relation, traffic-light state, scene change,
temporal context, or measured SCAN latency. No primitive is reconstructed or
invented from the scalar score. Candidate-to-reference overlap exists only for
the older cached reference through evaluation, not as the required V3 join.

## VERIFY paired-data audit

The three-clip Hangzhou probe has real physical inputs and costs, but uses the
older prompt hash `121874...f33`, older positive/negative schema, one video,
content-blind timestamps, and no representative candidate sample. Agreement
is 2/3. At the one disagreement, a qualitative audit found the 32B positive
unsupported, so 32B cannot be treated as an unquestioned teacher. There is no
V3 paired 8B/32B candidate dataset, no human-audited representative subset,
and no event-level K3 escalation evaluation.

## Leakage assessment

The new branch harness gives policies only public proxy values and labels
revealed by legal VERIFY actions; reference events remain evaluator-side.
States are grouped by domain/source, never randomly split by adjacent units.
Its output contains evaluator-derived Q targets only after rollout and never
feeds them back into the policy.
