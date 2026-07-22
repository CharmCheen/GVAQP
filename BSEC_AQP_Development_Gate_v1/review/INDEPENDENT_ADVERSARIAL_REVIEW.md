# Independent adversarial review

Reviewer: delegated independent agent `dasr_adversarial_review`

Initial verdict: `PASS_WITH_CAVEATS` for the frozen gate's mechanical, descriptive result; `FAIL` for a broad or statistically robust claim that DASR beats ARC.

## Reproduced evidence

- Frozen v3 and both final input hashes matched.
- Label-blind CLIP score/ranking and checkpoint identities checked out.
- Exact-B unique selections and normalized event-F1 AUCs independently reproduced.
- Rich interval: DASR `0.674074`, specified five-seed ARC adaptation `0.663854`, CLIP `0.641667`, NMS `0.655556`.
- Sparse interval: DASR and ARC both `0.222222`.
- Macro: DASR `0.448148`, ARC `0.443038`.
- BSEC, QTPC, and PNIR failures were preserved.

## Reviewer objections incorporated into the package

- The final intervals were previously labeled/evaluated; they are not called globally unseen.
- The comparator is named as `threshold-0.4 ARC-refinement + proxy-order exact-fill, shared K3`, not generic ARC.
- DASR lost to three of five ARC seeds, and seed variance exceeded the original rich-interval mean gap.
- DASR and stratified-only were identical in both final tests.
- The result was metric-specific and supported by only nine same-source VLM pseudo-events.
- The manifest and missing post-hoc generation script were repaired; the ARC seed audit now has a preserved runner.

The reviewer-permitted narrow claim is recorded in `REPORT.md`. The broader claim is rejected there, and the stronger pure-proxy counterexample motivated PSTR rather than being omitted.

## Follow-up PSTR verdict

Verdict: `PASS_WITH_CAVEATS` for status `PSTR_FROZEN_CANDIDATE_AWAITING_EXTERNAL_CONFIRMATION`.

The reviewer independently reproduced every PSTR selector, exact-B count, per-budget metric, AUC, pooled overhead, four-domain leave-one-domain-out result, and the 1,000-seed ARC audit. No selector leakage was found. The reviewer then identified an omitted public-proxy dataset3 domain and independently obtained PSTR `0.380363`, proxy top-k `0.354212`, and controlled shared-K3 ARC `0.250568`, while CLIP, NMS, DASR, and native ARC remained higher.

The review required dataset3 persistence; narrower wording; explicit proxy/version, ARC seeds, pooling, short-video, K3/evaluator, and strong-baseline contracts; a label-blind selection sealer; correction of the v4 `exact_oracle_calls` metadata defect; and machine-readable pure-proxy curves. These are addressed by the five-domain v2 outputs, proxy provenance audit, separate PSTR/DPP sealers, and frozen external protocol v5. The original v4 files remain immutable historical evidence; v5 is the terminal future-test contract.

Permitted conclusion: PSTR-5:4 is a deterministic, label-blind, exact-B candidate selected retrospectively on opened domains and frozen for a future independently sourced test. It shows consistent post-hoc advantage over pure proxy top-k and the specified shared-K3 ARC exact-fill comparator, but has no prospective external, human-ground-truth, native-ARC, or broad cross-video confirmation.
