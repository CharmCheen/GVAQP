
# Design decision ledger

| ID | Decision | Evidence / alternative | Rejection trigger |
|---|---|---|---|
| DD-01 | append-only surrogate, lambda=1 | symmetric TP/FP unit weight; sensitivities 0,2 auxiliary | revise only in a new preregistration |
| DD-02 | group FIFO confirm-as-soon-as-safe pi0 | current FIFO baseline; excludes learned scores | any hidden score/future dependency invalidates freeze |
| DD-03 | timestamp-ascending frozen scan units | simplest public deterministic iterator; unit manifest `bfbe4270936d267e36734b30174e83c47b0cb021cda3a9a9b6a7e7a7f709d182` | manifest/hash mismatch |
| DD-04 | reuse H-DS1 CONFIRM operational reserve but leave alpha unbound | separate 0.9 marginal profiles do not make their sum a complete-action 0.9 quantile | direct paired profile may bind alpha in a later freeze |
| DD-05 | block SCAN numeric binding | legacy `2.669129s` is composed from per-frame p95 and post-action adaptation | unblock only with existing or newly authorized direct full-obligation calibration |
| DD-06 | exact-model, zero-noise, zero-cost H-ROLLOUT1A | discriminates mechanism existence from approximation | any estimator/planning error moves study to 1B |
| DD-07 | complete SplitMix64 seed-to-episode sampler, split distributions, and disjoint seeds frozen | prevents implementation freedom and scenario cherry-picking | fixture/hash mismatch or post-hoc edits invalidate first-look claim |
| DD-08 | named scenarios diagnostic only | protects inference from hand-case selection | inclusion in primary aggregate invalidates gate |
| DD-09 | D4 dependency-blocked | D2 executable binding required by protocol | becomes ready only after D2 re-freeze and rehash |

Strongest conclusion: the scientific design is coherent, but physical pi0 is not executable under the requested safety semantics without a full SCAN obligation profile. Main competing explanation: the legacy allowance may be conservative in practice; it still does not establish the required calibrated object. Next action is a separately authorized, bounded SCAN-profile design/run—not a toy policy comparison. Reject this block only if an authoritative existing artifact is found that directly covers the complete SCAN obligation before admission.
