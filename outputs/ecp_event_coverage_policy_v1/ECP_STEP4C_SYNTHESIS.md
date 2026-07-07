# ECP Step 4c — T028c results synthesis (candidate ceiling + event-utility policy)

> Strict-replay where applicable, VLM-oracle-relative (IoU>=0.3). Sequel to
> `ECP_STEP4_SYNTHESIS.md`. T028c was split per plan: T028c-0 (candidate-level
> event-utility oracle ceiling) then T028c-1 (event-utility ranking policy).
> References: `t028c0_ceiling_report.md`, `t028c1_event_utility_policy_report.md`.

## T028c-0 — oracle ceiling (does the candidate set contain learnable signal?)

At each step ALL four candidate arms are enumerated and their offline marginal
event-utility computed (using true label + reference); the max-utility candidate
is executed. This is a CEILING (selection reads reference) — NOT strict-replay.

Result: the ceiling is valid (>= v2 everywhere it can act):
- **realcartest (proxy-informative)**: ceiling >= v2 on every cell; notably
  **+0.100 on realcartest_0_1570 @0.30** (0.300 vs 0.200) and **+0.143 on
  realcartest_3200_3830 @0.30** — exactly the two cells where v2 regressed vs v1.
  => the candidate set DOES contain event-level decisions better than v2 makes.
  => **learnable signal exists on proxy-informative segments -> T028c-1 justified.**
- **CERTIFY** is the highest-value arm (mean u=1.15, positive rate 1.0) but
  fires only 9 times — the CERTIFY candidate generator rarely triggers.
- **dataset3_0_1200 / dataset3_1200_2400**: ceiling ≈ v2 ≈ 0. The candidate
  generator (highest-proxy DISCOVER, gap-BRIDGE) **cannot propose the zero-proxy
  positives at all** — even a perfect selector over the proposed candidates
  cannot reach them. => **candidate-generator bottleneck**, not a policy
  problem. T028d/DR cannot fix this (no counterfactual support for arms never
  proposed).

## T028c-1 — event-utility ranking policy (strict replay)

Trained on the T028c-0 CANDIDATE-LEVEL utility table: every logged step carries
the offline marginal event-utility of ALL four candidate arms, so the learner
sees counterfactual arm utilities and is NOT confined to the logger's choices
(this is what made T028b merely re-learn the logger). GradientBoosting on
u(arm | state, arm); at each strict-replay step predict u for each available arm
and execute the max. Reference used only to build training labels offline.

Result (strict replay):
- **realcartest_3200_3830 @0.30: c1 0.286 = ceiling 0.286, beats v2 0.143** —
  the learned policy fully recovers the event v2 collapsed on.
- **realcartest_0_1570 @0.30: c1 0.250 vs v2 0.200** (between v1 0.300 and v2
  0.200; recovers most of the v2 regression, does not over-bridge).
- **realcartest_2000_3200 @0.10: c1 0.100 = ceiling = HTS, beats v2 0.050.**
- **dataset3_2400_3462: c1 0.111 > v2 0.000, = ceiling** — recovers events v2
  missed.
- **dataset3_0_1200 / 1200_2400: c1 ≈ v2 ≈ 0** — candidate-generator bottleneck
  confirmed; no policy trained on these candidates can recover zero-proxy
  positives.
- Precision: c1 holds v2-level precision on realcartest (no degradation).

**Verdict: T028c-1 is a strict-replay improvement over the fixed-weight v2 on
proxy-informative segments** — it recovers the ceiling on the cells v2 regressed
on, without losing precision. This is the first ECP variant to beat v2, and it
did so specifically because it was trained on EVENT-UTILITY (not positive-label,
not logger-confined), exactly as the user's plan argued.

## Honest scope

- T028c-1 is strict-replay compliant (reference only offline for labels; 0
  event_id leaks; 1 call/arm). It is a real method result, not a ceiling.
- The claim "ECP improves low-budget event coverage over B7-core" is now
  **PARTIALLY supported on proxy-informative realcartest** (c1 >= v2 >= ... and
  c1 recovers the ceiling on collapsed cells) but **still NOT supported on
  proxy-zero dataset3**, where the candidate generator — not the policy — is the
  blocker. Report per-segment; do not over-claim.
- T028d (IPS/DR) remains deferred: the user's reasoning holds — without
  randomized logging and recorded propensities, IPS/DR would just re-weight the
  logger and cannot create counterfactual support for zero-proxy arms the
  generator never proposes. The candidate-generator fix (proxy-free proposal
  mechanism) is the real open lever for dataset3, and it needs a new signal
  (small VLM batch or lightweight verifier), which is out of scope without
  authorization.

## Recommended next step

Do NOT run T028d yet. The informative next experiments are:
- **Improve the candidate generator** for the proxy-zero regime (e.g. a
  space-filling / low-discrepancy proposal mechanism that does not depend on
  proxy), then re-run T028c-0 to see if the ceiling rises on dataset3.
- Keep the event-utility ranker (T028c-1) as the policy layer; it is validated
  on proxy-informative segments.
- Only after a randomized logger + recorded propensities exist should T028d
  (IPS/SNIPS/DR) be attempted.
