# Candidate Coverage Gate V1 Result Interpretation

This is a read-only interpretation of existing `candidate_coverage_gate_v1` outputs. No new experiment, VLM inference, human audit, or training was run. All coverage values are VLM-defined pseudo-event evidence, not human ground truth.

Sanity checks all passed. Existing decision was `WEAK GO`.

Metric cell format below: `micro / macro / tail / source-HHI`.

Legend: `Rnd=random`, `TC=top_count`, `TNMS=temporal_nms_count`, `Rule=rule_like_conjunction`, `Rank=rank_fusion_proxy`, `SUnion=score_union_proxy`, `U=cheap_union_upper_bound`.

## Coverage By Gap And K

### Gap 0s
| K | Rnd | TC | TNMS | Rule | Rank | SUnion | U |
|---:|---|---|---|---|---|---|---|
| 5 | 0.01/0.00/0.00/0.46 | 0.05/0.12/0.00/1.00 | 0.03/0.08/0.00/0.52 | 0.03/0.01/0.00/0.52 | 0.00/0.00/0.00/0.52 | 0.02/0.04/0.00/0.52 | 0.10/0.18/0.00/0.26 |
| 10 | 0.01/0.01/0.01/0.36 | 0.07/0.17/0.00/0.52 | 0.07/0.25/0.33/0.46 | 0.03/0.01/0.00/0.50 | 0.02/0.08/0.17/0.30 | 0.07/0.13/0.00/0.42 | 0.13/0.34/0.33/0.26 |
| 20 | 0.02/0.03/0.03/0.32 | 0.11/0.34/0.33/0.46 | 0.11/0.26/0.33/0.42 | 0.05/0.01/0.00/0.47 | 0.07/0.17/0.17/0.27 | 0.10/0.18/0.00/0.27 | 0.23/0.37/0.33/0.32 |
| 50 | 0.05/0.06/0.07/0.29 | 0.23/0.37/0.33/0.48 | 0.23/0.30/0.33/0.69 | 0.11/0.04/0.00/0.41 | 0.34/0.26/0.17/0.43 | 0.21/0.37/0.33/0.29 | 0.51/0.46/0.33/0.42 |
| 100 | 0.10/0.11/0.11/0.28 | 0.57/0.47/0.33/0.69 | 0.38/0.36/0.33/0.36 | 0.41/0.29/0.17/0.39 | 0.51/0.48/0.33/0.36 | 0.41/0.42/0.33/0.39 | 0.74/0.55/0.33/0.38 |
| 200 | 0.21/0.20/0.21/0.28 | 0.74/0.57/0.33/0.35 | 0.44/0.39/0.33/0.33 | 0.70/0.56/0.33/0.34 | 0.64/0.53/0.33/0.36 | 0.62/0.52/0.33/0.39 | 0.87/0.70/0.50/0.32 |
| 500 | 0.49/0.49/0.48/0.28 | 0.95/0.74/0.50/0.32 | 0.75/0.64/0.50/0.28 | 0.90/0.72/0.50/0.31 | 0.85/0.70/0.50/0.31 | 0.89/0.72/0.50/0.31 | 0.98/0.99/1.00/0.28 |

### Gap 4s
| K | Rnd | TC | TNMS | Rule | Rank | SUnion | U |
|---:|---|---|---|---|---|---|---|
| 5 | 0.01/0.01/0.01/0.46 | 0.03/0.17/0.33/1.00 | 0.03/0.17/0.33/0.52 | 0.06/0.02/0.00/0.52 | 0.00/0.00/0.00/0.52 | 0.03/0.17/0.33/0.52 | 0.09/0.19/0.33/0.26 |
| 10 | 0.02/0.02/0.02/0.36 | 0.03/0.17/0.33/0.52 | 0.09/0.33/0.33/0.46 | 0.06/0.02/0.00/0.50 | 0.03/0.08/0.00/0.30 | 0.06/0.18/0.33/0.42 | 0.16/0.36/0.33/0.26 |
| 20 | 0.04/0.04/0.05/0.32 | 0.12/0.34/0.33/0.46 | 0.12/0.34/0.33/0.42 | 0.06/0.02/0.00/0.47 | 0.09/0.26/0.33/0.27 | 0.09/0.19/0.33/0.27 | 0.19/0.37/0.33/0.32 |
| 50 | 0.10/0.10/0.12/0.29 | 0.19/0.37/0.33/0.48 | 0.25/0.39/0.33/0.69 | 0.19/0.07/0.00/0.41 | 0.34/0.35/0.33/0.43 | 0.22/0.38/0.33/0.29 | 0.47/0.47/0.33/0.42 |
| 100 | 0.18/0.17/0.19/0.28 | 0.41/0.44/0.33/0.69 | 0.44/0.47/0.33/0.36 | 0.44/0.40/0.33/0.39 | 0.47/0.48/0.33/0.36 | 0.34/0.42/0.33/0.39 | 0.62/0.54/0.33/0.38 |
| 200 | 0.32/0.29/0.31/0.28 | 0.62/0.55/0.33/0.35 | 0.56/0.52/0.33/0.33 | 0.66/0.55/0.33/0.34 | 0.56/0.52/0.33/0.36 | 0.50/0.49/0.33/0.39 | 0.84/0.71/0.50/0.32 |
| 500 | 0.60/0.60/0.66/0.28 | 0.91/0.73/0.50/0.32 | 0.72/0.65/0.50/0.28 | 0.84/0.71/0.50/0.31 | 0.78/0.68/0.50/0.31 | 0.84/0.71/0.50/0.31 | 0.97/0.98/1.00/0.28 |

### Gap 8s
| K | Rnd | TC | TNMS | Rule | Rank | SUnion | U |
|---:|---|---|---|---|---|---|---|
| 5 | 0.01/0.01/0.01/0.46 | 0.03/0.17/0.33/1.00 | 0.03/0.17/0.33/0.52 | 0.07/0.03/0.00/0.52 | 0.00/0.00/0.00/0.52 | 0.03/0.17/0.33/0.52 | 0.10/0.19/0.33/0.26 |
| 10 | 0.02/0.02/0.02/0.36 | 0.03/0.17/0.33/0.52 | 0.10/0.33/0.33/0.46 | 0.07/0.03/0.00/0.50 | 0.03/0.08/0.00/0.30 | 0.07/0.18/0.33/0.42 | 0.17/0.36/0.33/0.26 |
| 20 | 0.05/0.04/0.05/0.32 | 0.14/0.35/0.33/0.46 | 0.14/0.35/0.33/0.42 | 0.07/0.03/0.00/0.47 | 0.10/0.26/0.33/0.27 | 0.10/0.19/0.33/0.27 | 0.21/0.38/0.33/0.32 |
| 50 | 0.11/0.10/0.12/0.29 | 0.21/0.38/0.33/0.48 | 0.24/0.39/0.33/0.69 | 0.14/0.06/0.00/0.41 | 0.31/0.35/0.33/0.43 | 0.21/0.38/0.33/0.29 | 0.41/0.46/0.33/0.42 |
| 100 | 0.19/0.17/0.19/0.28 | 0.34/0.43/0.33/0.69 | 0.41/0.46/0.33/0.36 | 0.38/0.38/0.33/0.39 | 0.45/0.48/0.33/0.36 | 0.31/0.42/0.33/0.39 | 0.59/0.53/0.33/0.38 |
| 200 | 0.34/0.30/0.31/0.28 | 0.59/0.54/0.33/0.35 | 0.55/0.52/0.33/0.33 | 0.62/0.55/0.33/0.34 | 0.52/0.51/0.33/0.36 | 0.45/0.48/0.33/0.39 | 0.83/0.71/0.50/0.32 |
| 500 | 0.61/0.61/0.66/0.28 | 0.90/0.73/0.50/0.32 | 0.69/0.65/0.50/0.28 | 0.83/0.71/0.50/0.31 | 0.76/0.68/0.50/0.31 | 0.83/0.71/0.50/0.31 | 0.97/0.98/1.00/0.28 |

## Increment Over Random

Average deltas over all K and gaps:

| Method | micro | macro | tail | HHI |
|---|---:|---:|---:|---:|
| TC | +0.180 | +0.234 | +0.152 | +0.220 |
| TNMS | +0.139 | +0.220 | +0.168 | +0.111 |
| Rule | +0.155 | +0.086 | -0.015 | +0.095 |
| Rank | +0.162 | +0.169 | +0.080 | +0.038 |
| SUnion | +0.139 | +0.191 | +0.136 | +0.044 |
| U | +0.319 | +0.354 | +0.263 | -0.004 |

The strongest signal is not any single primitive. It is complementarity: `U` is consistently above random and above most individual methods while adding almost no average source concentration.

## Stability, Leakage, And WEAK GO Cause

Stable across gaps: `TC`, `TNMS`, and `U` are consistently above random in micro and macro coverage. `Rank` becomes stable from K>=10 and is useful at K=50/100. `SUnion` is macro/tail-stable but not the best micro method. `Rule` has useful micro gain at K=100/200, but tail coverage is weak and small-K performance is poor.

Not stable enough for `GO`: the best single non-learned method changes with K/gap. At practical K, rank fusion often wins micro coverage; at larger K, rule-like conjunction can catch up; `top_count` remains very strong at K=100/200/500. Tail-source coverage is mostly stuck at 0.333 until the large union or K=500, so the gains are still head-source sensitive.

Learned methods are excluded because `top_learned_logreg` and `top_learned_rf` are marked `learned_reference=True` and were produced from conservative pseudo-label supervised GroupKFold. The exclusion is not merely a random-split/group-split concern; the evaluation pseudo-label itself entered training, so these scores are pseudo-label leakage for the main conclusion.

Precise `WEAK GO` trigger: micro gains exist, and union complementarity is real, but macro gains are modest, tail-source gains are weak, gap/K winners are not stable, and source concentration still shapes results. This is enough for mechanism development, not enough for a benchmark claim.

## Final Judgment

**A. 当前 benchmark 仍足够支持 symbolic-vs-proxy boundary study.**

Reason: it exposes a meaningful boundary between count/proxy ranking, rule-like kinematic signals, rank fusion, and candidate-union complementarity. It should be used as an engineering development set for symbolic-vs-proxy boundary analysis, not as final evidence of real risk-event retrieval.
