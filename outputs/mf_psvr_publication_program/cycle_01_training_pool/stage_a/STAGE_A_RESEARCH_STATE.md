# MF-PSVR Stage-A persistent research state

Status: `STAGE_A_COMPLETE_NOT_READY_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE`  
Independent review: `PASS`  
State hash: `e42d36b77e18ead8db17bd7f62f7a2554ceeeded315667dbfe4e3f3e50926a66`

## Current objective

Determine whether query-aligned candidate-value or temporal modeling on the exact frozen Stage-A evidence justifies entering an MF-PSVR V0/V1 physical pilot.

## Established findings

- [observed] Candidate extraction is exact and complete. Values: `{"detector_gpu_seconds": 939.6513740459993, "providers": 603, "score_rows": 5308, "track_rows": 28551, "units": 2654}`
- [observed] The frozen physical oracle execution completed without uncertainty or parse failure. Values: `{"accepted_calls": 96, "attempts": 96, "parse_failures": 0, "physical_cost_seconds": 2129.1209635050755, "projected_labels": 192, "uncertain": 0}`
- [observed_with_explicit_exception] The default frozen verifier fails only on one non-round-tripped CSV float; the unchanged frozen verifier fully passes with a parser-only round-trip shim. Values: `{"default_verify": "FAIL", "roundtrip_verify": "VERIFIED_COMPLETE_COMMIT"}`
- [observed] The query-aligned dataset contains 192 semantic rows; 172 are binary, with 24 positives overall and 61 full-rank aggregate features retained from 72 candidates. Values: `{"binary_rows": 172, "positive_rows": 24, "retained_features": 61, "semantic_rows": 192}`
- [observed_exploratory] M0 logistic is the development-pooled aggregate winner, but its macro-query advantage over raw YOLO is small and bootstrap-uncertain. Values: `{"macro_delta": 0.0328891250948338, "macro_delta_ci_95": [-0.094248463020642, 0.1530353988981815], "macro_query_auprc": 0.496672852759589, "pooled_auprc": 0.5554693466017564, "raw_macro_query_auprc": 0.4637837276647551, "raw_pooled_auprc": 0.1763995614498934, "selected": "M0_LOGISTIC"}`
- [observed_exploratory] Q1 M0 is indistinguishable from the selection-stratum control, while Q2 M0 is only slightly above raw YOLO. Values: `{"Q1_M0": 0.1676804957959973, "Q1_raw": 0.1180546687333904, "Q1_stratum_only": 0.1700986700986701, "Q2_M0": 0.8256652097231807, "Q2_raw": 0.8095127865961198, "pooled_stratum_only": 0.1973881050167815, "shuffled_p95_noisy": 0.2376785324885514}`
- [observed_exploratory] The best temporal model does not improve on the best aggregate model and is heterogeneous across queries. Values: `{"aggregate_auprc": 0.5554693466017564, "best_aggregate": "M0_LOGISTIC", "best_temporal": "TCN_TEMPORAL", "pooled_delta": -0.2198349739726821, "pooled_delta_ci_95": [-0.4200469791402433, 0.0487284990683749], "temporal_auprc": 0.3356343726290742}`
- [observed] The fixed audit is arithmetically excluded from fitting/selection and favors M0, but it is small and was not cryptographically blinded. Values: `{"audit_auprc": 0.8197781385281386, "audit_ece": 0.1325086319865586, "audit_positives": 8, "audit_rows": 28}`

## Derived conclusions

- Stage A does not justify V0/V1 physical-pilot execution.
- The decisive blocker is the frozen support STOP plus insufficient per-query positive/calibration support; the exploratory model metrics do not override it.
- The large pooled M0-versus-raw AUPRC difference is partly cross-query score harmonization and cannot be interpreted as uniform query-specific refinement.
- Aggregate temporal summaries remain the better current representation; a causal TCN/GRU adds complexity without demonstrated stable incremental value.
- Individual feature coefficients are hypothesis-generating associations only, despite label-free rank pruning.

## Active falsifiable hypotheses

- `H_TRANSPORTABLE_AGGREGATE_REFINEMENT`: A compact aggregate model can improve macro-query and per-query ranking on a second licensed query-enriched source. Prediction: Prospectively frozen grouped evaluation shows positive per-query deltas over raw YOLO and stratum-only controls, with group intervals excluding zero. Next test: Acquire a second licensed query-enriched dataset under identical Q1/Q2 semantics and preregister analysis before any oracle output is readable. Reject if: Either query fails to exceed its strongest raw/selection control or the macro-query paired interval continues to include zero.
- `H_Q1_REQUIRES_BETTER_QUERY_ALIGNED_SUPPORT`: Q1 weakness is dominated by sparse, selection-driven support rather than lack of usable visual signal. Prediction: More independent Q1-positive event groups improve performance beyond a frozen stratum-only baseline. Next test: Measure prospective Q1 lift after support enrichment; do not tune new mechanisms on the current 7-positive development subset. Reject if: Q1 remains at stratum-only performance after adequate independent positive-group support.

## Rejected hypotheses

- The lightweight temporal refiner is ready to replace aggregate features. Rejected here because: TCN_TEMPORAL minus M0_LOGISTIC pooled AUPRC is -0.219835, with no stable per-query gain.
- The pooled M0 lift demonstrates uniform learned refinement. Rejected here because: Q1 M0 (0.167680) is below stratum-only (0.170099); Q2 M0 (0.825665) is close to raw (0.809513); the macro paired interval spans zero.
- Final Platt calibration is deployable. Rejected here because: The calibration role has one positive total (Q1=1, Q2=0); all fitted final calibrators are explicitly non-deployable.
- Stage A supports immediate physical-pilot execution. Rejected here because: Frozen support decision STOP, only one dataset family, 7/9 development positives per query, and non-deployable calibration.

## Important failures and lessons

- The frozen oracle runner omitted a writer for a required physical-cost artifact; independent reconstruction was required and bound before finalization.
- The frozen verifier used default pandas float parsing with bit-exact comparison; preserve the default failure and round-trip-parser receipt together.
- The initial aggregate schema treated witness_class_id as ordinal and contained affine redundancies; categorical encoding plus label-free full-rank pruning is required.
- The modeling protocol was fixed after 70 readable oracle envelopes existed; all model/readiness/bootstrap evidence is exploratory, not preregistered.
- A pre-oracle-only candidate auditor initially lacked lifecycle-safe CLI behavior and accidentally overwrote three summary receipts; exact recovery and a non-mutating verify path are now documented.
- VERIFY budgets must count physical generic calls, not the two semantic projections returned by each call.

## Unresolved uncertainties

- Cross-dataset transport is unidentifiable with one dataset family.
- Natural-prevalence precision and recall are not identifiable from the enriched sample.
- The current positive count is too small for stable per-query feature attribution or calibration.
- Whether Q1 can exceed selection-stratum prevalence and whether Q2 can improve materially over raw YOLO require prospective evidence.
- Bootstrap intervals are conditional on fixed OOF predictions and do not include dataset-family uncertainty.

## Next highest-value action

Acquire one licensed query-enriched source dataset under the same frozen Q1/Q2 label semantics, freeze the provider/unit/oracle universe, and preregister grouped macro/per-query analysis before any oracle output is readable. Do not run V0/V1.

Authorization boundary: No additional oracle calls, acquisition, or V0/V1 physical-method execution is authorized by this state.

Handoff verification:

```bash
python scripts/finalize_mf_psvr_stage_a_research_state.py verify
```
