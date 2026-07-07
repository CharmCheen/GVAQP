# ECP Step 4 — T028 results synthesis (reweighting + offline learned policy)

> Strict-replay, VLM-oracle-relative (IoU>=0.3). Continuation of
> `ECP_STEPS1_3_SYNTHESIS.md`. T028 = ECP_DESIGN.md §6 Step 4 (reweight + learned
> policy). References: `t028a_ecp_bandit_report.md`, `t028b_ecp_learned_report.md`.

## T028a — reweighted hand-designed bandit (v1 -> v2)

Changes: BRIDGE weight 0.8 -> 1.2 and DISCOVER floor 0.05 -> 0.0 (so BRIDGE
wins when a bridge target exists); ZERO_PROXY no longer requires stagnation,
higher cap (0.25 -> 0.40, zp_thresh 0.5 -> 0.35).

Arm mix (v2):
- BRIDGE used 633 calls (vs 234 in v1) at 0.441 positive rate — the reweighting
  fixed the under-use identified in T026.
- ZERO_PROXY fired 48 calls (vs 6 in v1) at 0.125 positive rate — it now finds
  some positives in dataset3 where v1 found 0.

Recall/precision: v2 is **not** a clear win over v1. On most segments v2 == v1;
on two realcartest cells it is *lower* (realcartest_0_1570 @0.30: v2 0.200 vs
v1 0.300; realcartest_3200_3830 @0.30: v2 0.143 vs v1 0.286), and precision
also dropped there (1.000 -> 0.500). Boosting BRIDGE traded away DISCOVER
exploration and slightly hurt. **Conclusion: fixed-weight reweighting changes
the arm mix but does not reliably improve event recall/precision.**

## T028b — offline-learned contextual bandit

Policy: logistic regression on P(positive | state, arm) trained on the T026/v2
logged table (supervised-to-bandit reduction; biased by the v2 logging policy).
Evaluated under strict replay.

Result: **ECP-learned == ECP-v2 on essentially every segment x budget cell**
(identical recall and precision). The learned policy converged to the same
effective behavior as v2 (BRIDGE when available, else DISCOVER) and neither
regressed nor improved.

Why: offline learning from logged *choices* only re-learns the logger's
strategy; it has no counterfactual signal to beat the logger. This is the
standard offline-bandit limitation, now demonstrated empirically on this task.

## Honest overall status after T028

- Event-level arm selection is a **viable strict-replay policy layer** (T027):
  on proxy-informative realcartest it matches/beats HTS-EC-safe; on proxy-zero
  dataset3 it is weak (the discovery bottleneck, not the policy).
- **Fixed weights (T028a) and offline learning from logged choices (T028b) both
  fail to beat the hand-designed v2 / fixed executor reliably.** The levers that
  remain are: (1) a **richer reward** (event-recall/IoU marginal utility, not
  just positive-label) for the policy; (2) **interactive / exploratory** data
  rather than one logging policy; (3) the **proxy-zero dedicated arm** needs a
  real proxy-free signal, which offline learning cannot invent.
- The claim "ECP improves low-budget event coverage over B7-core" is **still not
  supported** after T028. ECP is a validated *structure* (event-level bandit
  above the executor) but not yet a *winning* method on these segments.

## Recommended next step (post-T028)

Do NOT re-run another fixed-weight sweep. The informative next experiments are:
- **T028c**: train the policy on **event-utility reward** (use the offline
  reference to label each logged step's marginal event_recall/IoU gain), not the
  positive label; this gives the bandit the ECP reward from ECP_DESIGN.md §2.3.
- **T028d**: a **doubly-robust / IPS** reweighting of the logged choices to
  correct the logging-policy bias before learning, instead of naive supervised
  reduction.
- Keep proxy-zero as a separate regime: only a proxy-free signal (new VLM on a
  few bins, or a lightweight verifier) can move dataset3_0_1200.

All strict-replay compliant: reference read only at final eval; 0 event_id
leaks; 1 oracle call per arm.
