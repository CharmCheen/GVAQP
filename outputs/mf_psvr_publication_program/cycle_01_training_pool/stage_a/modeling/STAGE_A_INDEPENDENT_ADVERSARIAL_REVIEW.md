# MF-PSVR Stage-A independent adversarial review

## Verdict

`PASS` for artifact integrity, recomputability, and the conservative handoff conclusion.

This is not a model-readiness pass. The scientific state remains `STAGE_A_FAIL_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE` / `NOT_READY_FOR_PHYSICAL_PILOT`. The corrected analysis is fully exploratory and post-hoc; its reused arithmetic `pool_audit` is not independent prospective validation.

## Decisive verification

- The repaired candidate verifier independently returned `PASS`: 603/603 providers, 2,654 units, 5,308 query-score rows, zero duplicate/missing/extra/invalid rows, and zero provider failures. The verify stage did not change the restored receipt hashes.
- The unchanged frozen oracle runner is content-bound at `f2461781...`. Its default pandas CSV parse still creates the documented one-ULP false negative. The parser-only round-trip wrapper is content-bound at `db6ebfe0...` and reran the full frozen verifier to `VERIFIED_COMPLETE_COMMIT`: 96 attempts, 96 accepted calls, zero uncertain calls, 96 call rows, and 192 label rows.
- Dataset verification recomputed exactly: 192 semantic rows, 172 binary rows, 24 positives, 96 physical calls, and 91 source/session groups.
- Modeling verification returned `PASS` and binds trainer `3b1b5451...`, dataset `85038f02...`, feature schema `942ec0b7...`, predictions `573d9bee...`, metrics `6230cee4...`, model manifest `864c75b3...`, final report `b132285e...`, and completion audit `d5761de8...`.
- Independent M0 refits reproduced all 144 development LOSO probabilities and all 28 fixed-audit probabilities bit-for-bit. No source/session group crosses roles; development and audit share zero groups. No audit row enters supervised fitting or current-run winner selection.

## Schema and leakage audit

The label-free schema retains 61 of 72 candidate features. The design rank with an intercept is exactly 62 on all 192 rows and independently on the 144 binary development rows. Development-only pruning selects the identical 61 columns. Raw numeric `witness_class_id` is absent from the effective schema and from all three serialized aggregate bundles; temporal models use a categorical one-hot class code.

The basis is full rank but ill-conditioned (condition number about `4.78e8`), so coefficient magnitudes remain unstable associations. The final report correctly avoids causal or independently identified feature-effect claims.

## Independent metric reconstruction

Every pooled metric and physical-call budget field recomputed from the prediction parquet with maximum absolute error `8.33e-17`.

- Development M0: pooled AUPRC `0.555469`, macro-query AUPRC `0.496673`.
- Development raw YOLO: pooled AUPRC `0.176400`, macro-query AUPRC `0.463784`.
- Selected-minus-raw: pooled `+0.379070`, but macro-query only `+0.032889`.
- At 16 physical calls, M0 recovers 7/15 positive development calls: precision `0.4375`, recall `0.4667`.
- Fixed audit contains only 14 binary physical calls; therefore budgets 16 and 32 correctly report `actual=14`. M0 recovers all 8 positive calls, with precision `0.5714` and recall `1.0`.

Query heterogeneity is decisive:

- Q1 development: M0 `0.167680`, raw `0.118055`, stratum-only `0.170099`, anchor-only `0.099663`.
- Q2 development: M0 `0.825665`, raw `0.809513`, stratum-only `0.359023`, anchor-only `0.269147`.
- Q1/Q2 fixed-audit M0 AUPRC: `0.411111` / `1.0`; ECE: `0.160823` / `0.112741`.
- Removing explicit query columns changes M0 development AUPRC by `-0.001286`; `NO_CLEAR_EXPLICIT_QUERY_GAIN` is supported.

The expanded controls recompute: shuffled-label M0 mean/p95 `0.142245/0.237679`, source-ID `0.111111`, session-ID `0.069313`, query-ID `0.101980`, selection-stratum `0.197388`, and anchor-ID `0.133199`. The 32 shuffled repetitions are only a noisy diagnostic, as the final report states.

## Bootstrap, temporal result, and readiness

The 2,000-replicate paired provider-session bootstrap reproduces exactly. Development selected-minus-raw pooled AUPRC has interval `[0.150389, 0.595345]`; its macro-query interval is `[-0.094248, 0.153035]`. The intervals are conditional on fixed OOF predictions and do not include winner-selection or cross-dataset uncertainty.

TCN is the best temporal network but not a demonstrated refinement: development pooled/macro AUPRC is `0.335634/0.382338`, and TCN-minus-M0 pooled AUPRC is `-0.219835` with interval `[-0.420047, 0.048728]`. Its per-query deltas are Q1 `+0.042168` and Q2 `-0.270837`. `NO_CLEAR_GAIN` is supported; no RGB backbone or YOLO was trained.

Readiness is correctly false. The oracle support gate fails; pooled development has only 16 positives; Q1/Q2 have only 7/9 development positives; and the final calibration role has one positive and 27 negatives, with zero Q2 positives. Serialized M1/TCN/GRU Platt maps are reproducibility artifacts, not deployable calibrators.

## Provenance and incident qualification

The initial modeling protocol existed before bulk parse/finalize, but 70 human-readable raw oracle envelopes already existed. The corrected trainer and correction suite postdate that protocol and the initial exploratory model run. Accordingly, only the following claim is allowed: supervised current-run fitting and winner selection arithmetically exclude `pool_audit`, while the entire corrected analysis remains post-hoc and exploratory. No preregistration, label blind, cryptographic blind, or independent holdout claim is allowed.

Label-free rank pruning inspected all feature rows, including audit covariates, although development-only pruning returns the identical schema. This creates no observed result difference but further prevents treating the audit as prospective validation.

During this review, a legacy candidate auditor ignored `--help` and transiently overwrote three summary receipts with downstream lifecycle false failures. Candidate payloads were unchanged. The exact original PASS receipts were restored, the auditor was changed to explicit `write`/non-mutating `verify` stages, and verification passed without changing receipt hashes. The incident is bound by `CANDIDATE_AUDITOR_LIFECYCLE_INCIDENT_AUDIT.json` (`a5cafc52...`, self-hash `d477662b...`).

One minor bootstrap limitation remains: 76/2,000 small fixed-audit resamples lack both classes for at least one query, and the implementation averages the remaining identifiable query slice. The development macro interval quoted in the final report has zero such replicates and reproduces exactly. Fixed-audit macro intervals should not be used as confirmatory uncertainty.

## Final-report audit and decision

All 34 mandatory result fields are present. The report separates semantic support failure from oracle execution commit, records the default frozen-verifier failure and round-trip exception, labels the modeling exploratory, reports physical-call budgets separately, includes pooled/macro/per-query results and nuisance controls, marks calibration non-deployable, and stops before V0/V1.

The strongest supported conclusion is therefore unchanged: the artifact chain is complete and trustworthy enough to support a stop decision, not a pilot. Acquire a second licensed/query-enriched dataset, preregister the prospective analysis and per-query gates before labels, preserve a genuinely unopened audit, and repeat grouped evaluation before any physical-method execution.

The companion JSON machine record has canonical self-hash `bd3e1db2c3546c249c001d04b635c11a6419a234f7bfc5950187787c68249498`.
