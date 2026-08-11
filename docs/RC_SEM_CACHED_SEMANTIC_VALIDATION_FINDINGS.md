# RC-SEM cached semantic validation findings

Status: `DEVELOPMENTAL_RETROSPECTIVE_NOT_CONFIRMATORY`

Decision: `NO_CACHED_EVIDENCE_OF_SAFE_SPECULATIVE_UPLIFT_REVISE_STATE`

## Question

Does RC-SEM return more true 32B-relative events, or return them earlier, than
verified-only ranking when both use the same cached semantic query evidence and
the probable-event precision floor is fixed at 0.80?

## Evidence used

Two inherited caches were evaluated without new GPU inference.

1. `partial_scan_pilot_v1`: two videos, offset-0 SCAN candidates, preserved
   Qwen3-VL-32B `TARGET_VEHICLE_CUT_IN` pseudo-reference events, and frozen
   candidate/reference matching. The posterior was trained on one video and
   evaluated on the other. Hidden candidate/reference matches were used by the
   evaluator only.
2. `clean_baseline_benchmark_v2`: 347 ten-second units from one video, five
   public YOLO/motion proxy features, 347 cached Qwen3-VL-32B
   `OBJECT_ENTERS_EGO_PATH` labels, and 27 materialized reference events. This
   cache was evaluated with 300-second blocked out-of-fold predictions.

The partial-scan prompt hash is
`19dc06ecb77c03d19320ed20a9c2281cbaa676b5a7f8112cf8eca2361311d370`.
The clean-cache prompt hash is
`12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`.

## Frozen retrospective procedure

- posterior family: standardized, median-imputed logistic regression;
- class balancing: training fold only;
- temporal calibration split: five 300-second grouped folds;
- cross-video folds: train long/test short and train short/test long;
- risk admission: at least ten training hypotheses and Wilson 95% precision
  lower bound at or above the required precision floor;
- primary floor: 0.80; sensitivity floors: 0.70 and 0.90;
- event scoring: deterministic one-to-one candidate/reference matching;
- VERIFY budgets: 5, 10, 20, 50 and 100 calls;
- comparison: raw-proxy verified-only, posterior verified-only, and RC-SEM;
- evaluator labels never enter posterior features or held-out threshold choice.

The actual RC-SEM `RiskControlledMaterializer` implementation was used for
probable publication. The experiment is deterministic under an independent
rerun.

## Results

### Risk-controlled probable publication

| Train | Held out | OOF ROC-AUC | OOF AP | Safe threshold | Probable events |
|---|---|---:|---:|---:|---:|
| PSP_V1_LONG | PSP_V0_SHORT | 0.665 | 0.300 | none | 0 |
| PSP_V0_SHORT | PSP_V1_LONG | 0.654 | 0.230 | none | 0 |

No threshold satisfied the 0.80 Wilson-LCB gate. Floors 0.70 and 0.90 reached
the same result. Therefore RC-SEM and posterior-ranked verified-only replay
have identical event recall and AnytimeEventRecallAUC at every tested budget:
safe speculative uplift is exactly zero in this cache.

### Unsafe apparent uplift

Removing the lower-confidence-bound requirement creates more output but breaks
the result-quality constraint.

| Held out | Gate | Returned | Matched | Event precision |
|---|---|---:|---:|---:|
| PSP_V0_SHORT | posterior mean >= 0.8 | 19 | 8 | 0.421 |
| PSP_V1_LONG | posterior mean >= 0.8 | 24 | 9 | 0.375 |
| PSP_V0_SHORT | raw candidate score >= 0.8 | 52 | 14 | 0.269 |
| PSP_V1_LONG | raw candidate score >= 0.8 | 116 | 45 | 0.388 |

These are not valid gains at a 0.80 precision requirement. The risk gate is
doing useful work by refusing them.

### VERIFY ranking

Posterior ranking has weak, nonuniform value. On `PSP_V0_SHORT`, posterior
ranking raises recall at budget 20 from 0.042 to 0.111 and at budget 100 from
0.375 to 0.417. On `PSP_V1_LONG`, it loses at some small budgets and has
slightly lower anytime AUC at budget 100 despite final recall changing from
0.204 to 0.209. This is not robust cross-video scheduling evidence.

### Second semantic query

For the 347-unit `OBJECT_ENTERS_EGO_PATH` cache, blocked out-of-fold ROC-AUC is
0.358 and average precision is 0.090 against a positive-unit prevalence of
0.115. No safe probable threshold exists. This independently argues that the
current cheap state is not aligned with the old 32B semantic predicate.

## Supported conclusion

The cached evidence supports the RC-SEM risk-control mechanism but not an
effect-size claim. The current implementation correctly refuses to call weak
proxy outputs probable events. Existing YOLO/motion features do not support
high-precision unverified materialization, so the present algorithm produces
no safe speculative improvement on these caches.

This is best classified as `REVISE_STATE`, not as a rejection of speculative
event return. The dominant bottleneck is the event posterior/state
representation, upstream of the materializer and controller.

## Main competing explanation

The caches ask older predicates (`CUT_IN` and `OBJECT_ENTERS_EGO_PATH`), not the
current V3 driver-response predicate. The partial-scan source benchmark also
reports `POLICY_INFORMATION_ISOLATION=FAIL`, and the clean benchmark is
provenance-blocked for 346 reused responses. Only two videos support the
cross-video test. Consequently this result may understate or overstate
performance on the authenticated V3 K3 relation.

## Next discriminating action

After the main V3 full grid and K3 reference are complete, build hypotheses at
the K3 event-lineage level and fit a posterior from causal features that encode
temporal persistence, lateral/path interaction, event fragmentation, scan
coverage, boundary uncertainty and revealed VERIFY history. Use three-video
leave-one-video-out calibration, then rerun the unchanged 0.80 Wilson-LCB gate.

Do not lower the precision floor. Reject or substantially revise probable-event
publication if the richer V3 event-level state still produces either:

- zero safe probable coverage in at least two held-out videos; or
- held-out probable precision below the frozen floor; or
- no anytime gain over verified-only after safe admissions exist.

## Artifacts

- `outputs/cached_semantic_validation/summary.json`
- `outputs/cached_semantic_validation/partial_fold_metrics.csv`
- `outputs/cached_semantic_validation/budget_metrics.csv`
- `outputs/cached_semantic_validation/unsafe_gate_ablations.csv`
- `outputs/cached_semantic_validation/evaluator_only_candidate_predictions.csv`
- `outputs/cached_semantic_validation/REPORT.md`
- `outputs/cached_semantic_validation/sensitivity_p70/`
- `outputs/cached_semantic_validation/sensitivity_p90/`

Reproduce with:

```bash
cd /root/charm/GVAQP_side_rcsem
PYTHONPATH=src python experiments/cached_semantic_validation.py \
  --repo-root /root/charm/GVAQP \
  --output-dir outputs/cached_semantic_validation
PYTHONPATH=src pytest -q
```
