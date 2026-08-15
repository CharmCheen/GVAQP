# Final mechanism audit — endogenous-scan root cause

## Bottom line

This audit could not proceed past the fact-check gate. The preflight it was
asked to explain — `outputs/endogenous_scan_preflight_v1/` with a "0/36 practical
SCAN-vs-VERIFY regret under substrate fidelity PASS and 5 natural exposure
misses" — does not exist in this repository, and several of its headline numbers
contradict the repository's own frozen source-of-truth.

## What I could and could not establish

Established (frozen, verified in this and prior audit):
- The audited (non-endogenous) substrate has 1475/1475 precomputed candidates,
  exposure recall 1.0, and 251 semantic-positive units all with candidates.
- Natural exposure false negatives are structurally impossible in the audited
  sequential environment (`SCAN_FALSE_NEGATIVE_AUDIT.md`).
- The faithful endogenous-SCAN stage (P4) is recorded `NOT_STARTED /
  NOT_AUTHORIZED` in `EXPERIMENT_DECISION_LEDGER.csv` and
  `NEXT_STAGE_STATE_MACHINE.md`.

Not established (unverifiable here):
- That any faithful endogenous-SCAN preflight ran, produced 57 prospective
  dual-legal states, 36 frozen counterfactual states, 5 natural misses, measured
  SCAN/VERIFY costs (0.1071 s / 18.444 s), or a 0/36 regret result.

## Why the causal audits A–G were not executed

Audits A (oracle headroom), B (miss recoverability), C (state support), D
(multi-horizon regret), E (cost-normalized macro-actions), F (information-to-
utility causal chain), and G (fresh VERIFY validation) all require the missing
preflight artifacts as input. Executing them here would require fabricating the
input data, which is explicitly forbidden by the task's own rules ("所有关键数字
必须追溯到 machine-readable artifacts / code"; no synthetic deletion; no
post-hoc redefinition). The only honest output is a blocked audit.

## Root-cause classification

Primary root cause: NOT DETERMINED (blocked by missing artifacts).

Secondary root cause: NOT DETERMINED (blocked by missing artifacts).

Formal classification: UNRESOLVED.

This is not "MIXED" (which would require actual evidence for multiple competing
mechanisms) and not any of the affirmative classifications. It is a
provenance/evidence gap, not a scientific conclusion.

## What the (unverifiable) 0/36 would and would not mean

If the preflight is later provided and the 0/36 result is confirmed against
machine-readable artifacts:

- It would NOT by itself falsify the original endogenous-SCAN theory, because a
  single preflight with a specific utility threshold (delta 0.02) and a specific
  action granularity (SCAN1 vs VERIFY1) cannot distinguish headroom-limited from
  recoverability-limited from granularity-limited from horizon-washout.
- It WOULD, at most, update the prior that the specific SCAN1-vs-VERIFY1
  formulation has no practical terminal-quality headroom on that workload.

None of these interpretations are endorsed here, because the evidence is absent.

## Controller reopen gate

CONTROLLER_REOPEN_CANDIDATE = NO. CONTROLLER TRAINING AUTHORIZED = NO.
MAB/RL AUTHORIZED = NO. These are unchanged regardless of the missing
artifacts; the gate has not been met.

## Claim-B interpretation

UNCHANGED. Claim B remains NOT ESTABLISHED. No new supporting or disfavoring
evidence could be admitted from this audit because the cited preflight is
missing.

## Human P1 isolation

HUMAN P1 = UNCHANGED / NOT_TOUCHED. No human annotation records, event counts,
or P1 analysis were read; no P1 protocol or frozen pairs were modified.

## Next single scientific action

Resolve the provenance conflict: locate and provide
`outputs/endogenous_scan_preflight_v1/` (or the environment that contains it).
Only after the artifacts are present and the fact-check passes can the root-cause
audit continue.
