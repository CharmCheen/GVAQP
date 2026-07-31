# RC-SEM cached semantic validation

Decision: `NO_CACHED_EVIDENCE_OF_SAFE_SPECULATIVE_UPLIFT_REVISE_STATE`

This is retrospective developmental evidence only. The risk-controlled gate
was tested without exposing held-out labels to the posterior model or threshold
selection, but the inherited source benchmarks have the limitations bound in
`summary.json`.

## Risk gate result

- PSP_V1_LONG -> PSP_V0_SHORT: OOF ROC-AUC 0.665, AP 0.300; safe threshold found=False; probable events=0.
- PSP_V0_SHORT -> PSP_V1_LONG: OOF ROC-AUC 0.654, AP 0.230; safe threshold found=False; probable events=0.

The 0.80 Wilson-LCB gate admitted no speculative events in either fold.
Consequently RC-SEM and posterior-ranked verified-only replay have identical
recall and anytime AUC at every tested VERIFY budget. Unsafe mean/raw-score
thresholds do return events, but their held-out precision is recorded in
`unsafe_gate_ablations.csv` and is below the required floor.

## Second-query diagnostic

The 347-unit `OBJECT_ENTERS_EGO_PATH` cache has blocked OOF ROC-AUC 0.358 and AP 0.090. No safe risk threshold was found.

## Interpretation

The cache does not falsify the risk-control logic: it shows that the logic
correctly refuses an unsupported probable-event claim. It does falsify the
working assumption that the existing YOLO/motion proxy state is already
sufficient to produce high-precision unverified events. The next discriminating
change is an event-level posterior/state representation, not a looser gate.

## Reproduction

```bash
cd /root/charm/GVAQP_side_rcsem
PYTHONPATH=src python experiments/cached_semantic_validation.py \
  --repo-root /root/charm/GVAQP \
  --output-dir outputs/cached_semantic_validation
```

## Budget table

```text
                            anytime_event_recall_auc                                                           event_recall                                               
method                       POSTERIOR_VERIFIED_ONLY RAW_PROXY_VERIFIED_ONLY RC_SEM_RISK_CONTROLLED POSTERIOR_VERIFIED_ONLY RAW_PROXY_VERIFIED_ONLY RC_SEM_RISK_CONTROLLED
heldout_video verify_budget                                                                                                                                               
PSP_V0_SHORT  5                             0.011111                0.011111               0.011111                0.027778                0.027778               0.027778
              10                            0.027778                0.019444               0.027778                0.069444                0.027778               0.069444
              20                            0.059028                0.025694               0.059028                0.111111                0.041667               0.111111
              50                            0.133333                0.074444               0.133333                0.236111                0.180556               0.236111
              100                           0.219167                0.178889               0.219167                0.416667                0.375000               0.416667
PSP_V1_LONG   5                             0.006122                0.009184               0.006122                0.010204                0.015306               0.010204
              10                            0.011735                0.012245               0.011735                0.025510                0.015306               0.025510
              20                            0.022449                0.021684               0.022449                0.040816                0.045918               0.040816
              50                            0.048776                0.050612               0.048776                0.091837                0.091837               0.091837
              100                           0.101633                0.102347               0.101633                0.209184                0.204082               0.209184
```
