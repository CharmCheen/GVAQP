# Proposed State-of-Truth Update (auditor proposal; NOT applied)

This document proposes, but does not perform, updates to the root state
files. Per the audit mandate, `PROJECT_STATE_OF_TRUTH.md`,
`CLAIM_LEDGER.csv`, `EXPERIMENT_DECISION_LEDGER.csv`,
`ACTIVE_HYPOTHESES.md`, `CLOSED_BRANCHES.md`, and
`NEXT_STAGE_STATE_MACHINE.md` were NOT modified.

## What the audit verified (no change needed, strength confirmed)

- All headline numbers in the frozen ledgers that we checked re-derived
  exactly (56/56 deterministic checks; see VERIFICATION_RESULTS.json):
  ranking gap 0.095134, exposure gap 0.0, AUPRC 0.2584–0.3146, 1475/1475
  candidates, 251 positives, K3-vs-K0 40/14/0 with median +0.1457, gap-only
  +0.1377 with 0.0 for all complex K3 marginals, monotonicity 0.48%,
  108-state 25/26/57 and 5/5/98 (reconciled thresholds), learned vs fixed
  regret 0.009693 vs 0.000885, shadow 198 pairs / 2-2-2 clusters / MAE gain
  0.000665, P2 median 0.0 with CI [-0.0136, 0.0223], P1 automated counts
  1008/198/12, human label rows = 0.
- Protocol hashes for four frozen protocol families verified byte-exact;
  cited physical-probe sha256s match local files.

## Proposed additions (recommended for owner review)

1. **Provenance flag for the endogenous preflight.** Add a row or note
   recording that a claimed `outputs/endogenous_scan_preflight_v1/` is
   absent locally and REPORTED_REMOTE_UNVERIFIED, so future agents do not
   re-derive this. Recommended placement: CLAIM_LEDGER (new row C-L with
   status UNVERIFIABLE) or a provenance section of PROJECT_STATE_OF_TRUTH.md.
2. **Disambiguation of the two 108-state decompositions.** Add one sentence
   clarifying 25/26/57 (tie tolerance 1e-12) and 5/5/98 (practical delta
   0.005) are two threshold views of the same delta_q table, not two
   experiments.
3. **Correction of the pilot-video naming.** The prior root-cause audit
   states the physical pilot used "PSP_V0_SHORT/PSP_V1_LONG (not
   DALI/HANGZHOU/WUHAN)". Hash evidence shows PSP_V0_SHORT = WUHAN and
   PSP_V1_LONG = DALI. Recommend correcting any downstream text that
   repeats the "not DALI/WUHAN" claim.
4. **Wording guard on C-A scope.** The word "proxy" in C-A currently
   invites reading beyond the verified ranking scope; recommend the scope
   column explicitly say "ranking degradation over a fully precomputed
   universe; natural acquisition failure unmeasured".

## Proposed no-ops (explicitly do NOT change)

- Do NOT change C-B/C-K from NOT ESTABLISHED (the unverifiable 0/36 changes
  nothing).
- Do NOT reopen controller/MAB/RL (unchanged NO-GO / CLOSED).
- Do NOT alter human P1 status (WAITING_HUMAN_REFERENCE; 0 labels).
- Do NOT add an experiment-ledger row implying a faithful endogenous
  preflight completed.
- Do NOT perform root-cause analysis of the 0/36 without recovered
  artifacts.

## Condition that would supersede this proposal

Recovery + hash verification of the 13 preflight artifacts from the prior
environment; only then may the project owner decide whether to record the
preflight in the ledgers.
