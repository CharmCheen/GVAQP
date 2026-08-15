# Preliminary fact check — CONFLICT

Result: **CONFLICT** (missing artifacts; premise not verifiable in this
repository).

Per the task's section 0 and section 28, this report is produced instead of
continuing the causal interpretation, because the "current primary facts" cannot
be traced to machine-readable artifacts or code.

## What was required to verify

The task lists these "primary facts" and requires them to be re-verified from
artifacts:

- SUBSTRATE_FIDELITY = PASS
- VIDEOS = DALI / HANGZHOU / WUHAN; INDEPENDENT_SOURCE_VIDEOS = 3
- CHEAP_SCAN = fresh raw-video decode + frozen YOLOv8n candidate generation
- SCAN_MEDIAN_COST ~ 0.1071 s; VERIFY_MEDIAN_COST ~ 18.4440 s; ratio ~ 172.29
- SEMANTIC_POSITIVE_UNITS = 251
- NATURAL_UNIT_EXPOSURE_RECALL = 246/251 ~ 0.9801
- MODEL_RELATIVE_EVENT_EXPOSURE_RECALL = 182/185 ~ 0.9838
- NATURAL_MISSES = 5; ZERO_EXPOSURE_MODEL_RELATIVE_EVENTS = 3
- MISSES_SPAN = 3/3 source videos; MISS TAXONOMY = no_relevant_object_class
- PROSPECTIVE_DUAL_LEGAL_STATES_LOGGED = 57
- FROZEN_COUNTERFACTUAL_STATES = 36
- PRIMARY_REGRET_THRESHOLD delta = 0.02
- SCAN_BETTER = 0/36; VERIFY_BETTER = 0/36; INDIFFERENT = 36/36
- MEDIAN_ABS_DELTA ~ 0.01478

## Verification result per item

| Claimed fact | Verifiable in repo? | Status |
|---|---|---|
| `outputs/endogenous_scan_preflight_v1/` exists | No | ABSENT |
| ENDOGENOUS_SCAN_PREFLIGHT_REPORT.md | No | ABSENT |
| DECISION.json / WORKLOAD_FREEZE.json / CHEAP_SCAN_CONTRACT.json / BEHAVIOR_POLICY_CONTRACT.json | No | ABSENT |
| NATURAL_EXPOSURE_RESULTS.csv / NATURAL_EXPOSURE_MISSES.csv | No | ABSENT |
| PROSPECTIVE_STATE_LOG.csv / COUNTERFACTUAL_STATE_MANIFEST.csv | No | ABSENT |
| ACTION_BRANCH_RESULTS.csv / ACTION_REGRET_BY_STATE.csv / ACTION_REGRET_BY_VIDEO.csv | No | ABSENT |
| PHYSICAL_COST_PROFILE.csv | No | ABSENT |
| SEMANTIC_POSITIVE_UNITS = 251 | Yes (identifiability audit) | EXISTS |
| NATURAL_UNIT_EXPOSURE_RECALL = 246/251 | No | CONTRADICTED (exposure recall = 1.0 by construction) |
| SCAN/VERIFY costs 0.1071 / 18.4440 / 172.29 | No | ABSENT (only unrelated coincidental matches) |
| 5 natural misses, 3 zero-exposure events, no_relevant_object_class taxonomy | No | ABSENT |
| 57 prospective states / 36 frozen counterfactual states | No | ABSENT |
| 0/36 practical regret at delta 0.02 | No | ABSENT |

## The only fully verifiable item is the one that contradicts the premise

`SEMANTIC_POSITIVE_UNITS = 251` exists and matches. But the frozen identifiability
audit states candidate exposure recall is 1.0 and 251/251 positives have
candidates, and that natural SCAN false negatives are impossible in the audited
environment. A "natural unit exposure recall of 246/251" (5 misses) therefore
cannot be an artifact of the audited environment; it would require a faithful
endogenous-scan substrate that the ledger records as `NOT_STARTED`.

## Interpretation of the conflict

Three mutually exclusive explanations, in order of likelihood given available
evidence:

1. The preflight was run in a different machine/worktree (`/root/charm/GVAQP`
   and `/root/charm/GVAQP_side_rcsem`) that is not present in this environment.
2. The preflight is described but was never actually committed/persisted.
3. The preflight numbers are a forward-looking specification, not a recorded
   result.

In all three cases, the causal audits (A–G) cannot be executed here without
either locating the missing artifacts or fabricating data, and fabrication is
explicitly prohibited.

## What would resolve the conflict

Provide (a) the missing `outputs/endogenous_scan_preflight_v1/` artifacts, or
(b) the absolute path of the environment that contains them. Until then, this
audit remains blocked and no root-cause classification is issued.
