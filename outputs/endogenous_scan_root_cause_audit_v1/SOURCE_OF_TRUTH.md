# Endogenous-scan root-cause audit — source of truth

This file records exactly what this audit checked, what it found, and what it
could not find. It is the audit's own provenance ledger.

## Environment discrepancy

The task prompt opens with "继续 `/root/charm/GVAQP`" and the preflight manifest
referenced in prior artifacts points at `/root/charm/GVAQP_side_rcsem`. Neither
path exists in this environment. The actual repository is at
`/Users/charmcheen/FDU/入学前/GVAQP`. This path discrepancy is itself a
first-order provenance finding.

## Checks performed

1. Directory existence: `outputs/endogenous_scan_preflight_v1/` — **absent**.
2. Repo-wide filename search for all 13 preflight artifacts named in the task
   (`ENDOGENOUS_SCAN_PREFLIGHT_REPORT.md`, `DECISION.json`, `WORKLOAD_FREEZE.json`,
   `CHEAP_SCAN_CONTRACT.json`, `BEHAVIOR_POLICY_CONTRACT.json`,
   `NATURAL_EXPOSURE_RESULTS.csv`, `NATURAL_EXPOSURE_MISSES.csv`,
   `PROSPECTIVE_STATE_LOG.csv`, `COUNTERFACTUAL_STATE_MANIFEST.csv`,
   `ACTION_BRANCH_RESULTS.csv`, `ACTION_REGRET_BY_STATE.csv`,
   `ACTION_REGRET_BY_VIDEO.csv`, `PHYSICAL_COST_PROFILE.csv`) — **0 of 13 found**.
3. Exact numeric probes for the task's "primary facts"
   (`0.9801`, `0.9838`, `246/251`, `182/185`, `172.29`, `18.444`, `0.1071`,
   `0.01478`) — only coincidental hits in unrelated experiments
   (`DARE_AQP_Experiment_v1`, `late_aqp_*`, `risk_limiting_*`), none in any
   endogenous-scan preflight.
4. String probes for `NATURAL_EXPOSURE`, `NATURAL_MISSES`,
   `no_relevant_object_class`, `PROSPECTIVE_STATE_LOG`,
   `COUNTERFACTUAL_STATE_MANIFEST` — none present.
5. Git state: single branch `main` (plus `origin/dspro`), no stashes, no
   uncommitted endogenous-scan work. Latest commit `973900696` ("Consolidate
   GVAQP research state and experiment artifacts").

## Existing frozen facts that contradict the task premise

From `outputs/original_theory_identifiability_audit_v1/`:

- `CANDIDATE_EXISTENCE_AUDIT.md`: 1475/1475 candidates precomputed; 0 generated
  by SCAN; candidate exposure recall 1.0.
- `SCAN_FALSE_NEGATIVE_AUDIT.md`: "Natural `SCAN failed -> candidate never enters
  frontier` is impossible in the audited sequential environment"; 251 semantic
  positives all have candidates; natural exposure false negatives are not
  measurable in the audited environment.
- `EXPERIMENT_DECISION_LEDGER.csv` row `P4_FAITHFUL_SCAN`:
  status `NOT_STARTED`, `No faithful substrate result exists`, `NOT_AUTHORIZED`.
- `NEXT_STAGE_STATE_MACHINE.md`: P4 faithful endogenous SCAN is
  `DEFERRED / NOT AUTHORIZED`.

These state that no faithful endogenous-SCAN substrate has been run, which
directly contradicts the task's "SUBSTRATE_FIDELITY = PASS" and "natural exposure
recall 246/251" premises.

## What does exist that is adjacent

- `benchmarks/partial_scan_pilot_v1/` is a physical scan benchmark pilot on
  `PSP_V0_SHORT` / `PSP_V1_LONG` (not DALI/HANGZHOU/WUHAN). Its terminal decision
  is `OVERALL_PARTIAL_SCAN_BENCHMARK = BLOCKED` with `POLICY_INFORMATION_ISOLATION
  = FAIL`, and it uses a pseudo-reference, not the model-relative K3 reference.
  It contains no "57 prospective dual-legal states" or "36 frozen counterfactual
  states".
- `outputs/public_state_predictability_cached_v3/` is the 108-state cached
  (non-endogenous) predictability audit, on two source videos with abstract
  costs.

Neither of these is the cited `endogenous_scan_preflight_v1`.

## Conclusion of this source-of-truth pass

The evidence for the "0/36 practical regret under a faithful endogenous-SCAN
substrate with 5 natural exposure misses" claim is absent from this repository.
Per the task's own gate, the causal interpretation must stop until the conflict
is resolved.
