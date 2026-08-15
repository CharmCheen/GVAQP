# Endogenous-SCAN Preflight Provenance Audit

## Decision

**ENDOGENOUS_SCAN_PREFLIGHT_STATUS = REPORTED_REMOTE_UNVERIFIED**
(candidate classification; evidence for the claim itself is MISSING locally)

The claimed `outputs/endogenous_scan_preflight_v1/` artifact set does not
exist in this checkout. This re-confirms the prior local root-cause audit
(`outputs/endogenous_scan_root_cause_audit_v1/`, untracked), whose blocked
conclusion we independently reproduced.

## What was searched (this audit, fresh)

1. Directory `outputs/endogenous_scan_preflight_v1/` — ABSENT.
2. All 13 named artifacts
   (`ENDOGENOUS_SCAN_PREFLIGHT_REPORT.md`, `DECISION.json`,
   `WORKLOAD_FREEZE.json`, `CHEAP_SCAN_CONTRACT.json`,
   `BEHAVIOR_POLICY_CONTRACT.json`, `NATURAL_EXPOSURE_RESULTS.csv`,
   `NATURAL_EXPOSURE_MISSES.csv`, `PROSPECTIVE_STATE_LOG.csv`,
   `COUNTERFACTUAL_STATE_MANIFEST.csv`, `ACTION_BRANCH_RESULTS.csv`,
   `ACTION_REGRET_BY_STATE.csv`, `ACTION_REGRET_BY_VIDEO.csv`,
   `PHYSICAL_COST_PROFILE.csv`) — 0 found anywhere in the repo.
3. Keyword probes `NATURAL_EXPOSURE_RESULTS`, `NATURAL_EXPOSURE_MISSES`,
   `ACTION_REGRET_BY_STATE`, `COUNTERFACTUAL_STATE_MANIFEST`,
   `PHYSICAL_COST_PROFILE`, `ENDOGENOUS_SCAN_PREFLIGHT_REPORT` — only hits
   inside the prior blocked audit that names them as missing.
4. Numeric probes (`0.1071`, `18.4440`, `172.29`, `246/251`, `182/185`,
   `0.9801`, `0.9838`) — no endogenous-preflight source; only unrelated
   coincidental matches in legacy experiments.
5. Git: single branch `main` (+`origin/dspro`), no worktrees, no stashes,
   no tags; reflog shows only clone + fast-forward pull. The two audit
   directories (`ccf_independent_research_audit_v1`,
   `endogenous_scan_root_cause_audit_v1`) are untracked local files.

## Reported numbers — NOT verifiable, DO NOT assume true

| Reported claim | Local verification |
|---|---|
| SUBSTRATE_FIDELITY = PASS | NO substrate artifact exists |
| SCAN_MEDIAN_COST ≈ 0.1071 s; VERIFY_MEDIAN_COST ≈ 18.4440 s; ratio ≈ 172.29 | ABSENT. Closest local physical data: partial-scan pilot warm median ~1.18–1.21 s per SCAN action (different machine/operator) |
| SEMANTIC_POSITIVE_UNITS = 251 | EXISTS and matches (1475-unit substrate) — but that number belongs to the audited precomputed substrate |
| UNIT_EXPOSURE_RECALL = 246/251 ≈ 0.9801 | CONTRADICTED for the audited substrate (recall = 1.0 by construction; 251/251 have candidates) |
| EVENT_EXPOSURE_RECALL = 182/185 ≈ 0.9838 | ABSENT |
| NATURAL_MISSES = 5 | ABSENT; natural misses are structurally impossible on the audited substrate |
| FROZEN_COUNTERFACTUAL_STATES = 36; PROSPECTIVE = 57 | ABSENT |
| SCAN_BETTER = 0; VERIFY_BETTER = 0; INDIFFERENT = 36 (delta 0.02) | ABSENT |
| MEDIAN_ABS_DELTA ≈ 0.01478 | ABSENT |

## Why the 0/36 cannot be interpreted (and must not be root-caused)

- A "natural exposure recall < 1" result cannot arise from the audited
  one-candidate-per-unit substrate; it requires the faithful endogenous
  substrate that the project ledger records as `P4 = NOT_STARTED /
  NOT_AUTHORIZED` (`EXPERIMENT_DECISION_LEDGER.csv`,
  `NEXT_STAGE_STATE_MACHINE.md`).
- Three mutually exclusive explanations, none verifiable locally: (a) the
  preflight ran in another environment (`/root/charm/GVAQP` or
  `/root/charm/GVAQP_side_rcsem`, the paths recorded in the prompt and in
  `RC_SEM_PACKAGE_MANIFEST.json`), (b) it was described but never committed,
  (c) the numbers are a forward specification, not a recorded result.

## Consequence

- ROOT-CAUSE ANALYSIS OF THE 0/36: **NOT AUTHORIZED** (evidence absent).
- CAN THE 0/36 RESULT BE USED SCIENTIFICALLY: **NO** (unverifiable; and even
  if recovered, a single preflight at delta 0.02 with one action granularity
  could not falsify the theory — at most it would bound the specific
  SCAN1-vs-VERIFY1 formulation).
- Claim B and C-K remain NOT ESTABLISHED — unchanged by this audit.
- Controller remains CLOSED; MAB/RL remain unauthorized.

Recovery requirements are enumerated in
`REMOTE_ARTIFACT_RECOVERY_MANIFEST.md`.
