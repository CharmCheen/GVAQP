# Codex Audit Final Report

## Executive Summary

GLM's core label files are mostly valid: dataset3 full center10 oracle is complete and temporal clustering is real. However, the proxy analysis has a material AUROC bug and the budget replay omits the recomputed strongest single feature (`object_count_mean`). The main problem is not only claim inflation; Stage 3 and Stage 5 need no-new-VLM recomputation before paper-level method conclusions.

## File Integrity

The actual main directory is `garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1`, not `garc_eval/outputs/autonomous_sprint_v1/`. The full parsed oracle CSV, 297 new per-anchor JSON files, 50 P1 reused labels, analysis CSVs, replay CSV, reports, scripts, and logs exist. `method_by_budget_summary.csv` is absent.

## Experiment Completion

Stages 1-5 were materially executed. Stages 6-9 are design/reporting/literature synthesis. DCA is proposed but not replayed. Certificate/audit is not implemented.

## Numeric Recheck

- Full oracle: 347 anchors, 40 positives, 307 negatives, positive rate 0.115274.
- P1 reuse: 50 reused rows; new raw JSON files: 297.
- Positive clusters: 27 total, 21 singleton, 6 multi-anchor, largest 9.
- Temporal correlation: P(1->1)=0.325; base=0.115.
- Best recomputed proxy AUROC: `object_count_mean`=0.627; score-fusion AUROC=0.550; object_count_mean AUROC=0.627.

## Dataset3 Mainline Support

Dataset3 supports the AQP mainline as a pseudo-oracle clip retrieval benchmark: it is non-vacuous, semantically different from realcartest, and budget allocation matters. It does not yet support GLM's specific proxy-failure explanation because the object-count AUROC was miscomputed.

## Proxy Oracle Relation

The data strongly supports `score_fusion != semantic event`. But GLM's broader proxy diagnosis is partly wrong: `object_count_mean` is not anti-predictive and should have been included in budget replay.

## Temporal And Cluster Evidence

Temporal correlation is above base rate and cluster-level metrics are justified. However, most clusters are singletons, so methods relying on local expansion need direct validation.

## Budget Replay

The replay supports `proxy_diversity_prefilter` as the safest current method only within the score-fusion replay family. At B=80 it improves anchor recall from 0.250 to 0.325 over score-fusion top-proxy, but `object_count_mean` top-B finds 15/40 positives at B=80. `cluster_aware_selection` is only an oracle upper bound. `hybrid_explore_exploit` is not reproducible enough for strong claims because it used unseeded randomness with one repeat.

## Boundary And REFINE Risk

Boundary localization is not solved. Dataset3 positives are templated around 0.0-0.7; event IoU and REFINE claims are unsafe. Decision: `BOUNDARY_ORACLE_REDESIGN_REQUIRED`.

## Audit Certificate State

No clip-level recall certificate or temporal-correlation CI is implemented in this sprint. Certificate language must be future-work or planned-method language only.

## Related Work Boundary

Position against SUPG carefully: closest AQP/certificate baseline, but frame/i.i.d. assumptions differ from temporally correlated semantic event clips. STRIVE-D requires manual verification before strong novelty statements.

## Paper-Safe Claims

- Complete dataset3 pseudo-oracle reference.
- Weak/nonmonotone score-fusion proxy on semantic events.
- Temporal correlation and event clustering in clip labels.
- Budget decomposition/diversity prefilter can beat score-fusion top-proxy on dataset3 at selected budgets.

## Unsafe Claims

- DCA as validated main algorithm.
- REFINE as contribution.
- Formal certificate implemented.
- Human-ground-truth risk-event claims.
- Cluster-aware as deployable.
- `object_count_mean` anti-predictive or score-fusion AUROC=0.624.
- Best non-oracle method before replay is recomputed with corrected proxy baselines.

## Recommended Main Algorithm

Current paper method should not yet be promoted beyond a score-fusion budget-decomposition result. Recompute Stage 3/5 first; then decide whether diversity prefilter or an object-count/coverage hybrid is the main method. DCA remains a next algorithm variant motivated by diagnostics.

## Next Minimum Experiment

Fix AUROC and rerun no-new-VLM Stage 3/5 with `object_count_mean`, score-fusion, diversity prefilter variants, fixed seeds, and saved selected anchors. Then implement/replay DCA and run a minimal no-repair certificate mechanics simulation on existing labels.

## Human Check List

- Manually verify STRIVE-D/closest related work overlap.
- Inspect a small sample of dataset3 positive/negative raw VLM JSONs for semantic plausibility.
- Review paper draft wording for DCA/certificate/REFINE overclaims.

## Numbers Or Wording To Fix

- Replace 18 singleton / 9 multi-anchor clusters with 21 / 6.
- Replace GLM AUROC values: score_fusion recomputes to 0.550, object_count_mean to 0.627; remove the anti-predictive object-count claim.
- Remove or qualify DCA validation language.
- Mark `cluster_aware_selection` as oracle upper bound everywhere.
- Remove event-IoU claims from dataset3 boundary fields.

FINAL_DECISION: GLM_RESULTS_PARTIAL_NEED_RECOMPUTE
