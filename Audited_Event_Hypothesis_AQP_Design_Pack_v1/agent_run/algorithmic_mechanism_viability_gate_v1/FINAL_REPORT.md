# Algorithmic Mechanism Viability Gate v1

Decision: `IDEAL_SIGNAL_ONLY`

## Scope and integrity

This is synthetic and evaluator-derived semi-synthetic evidence, not real online video performance. Physical VLM calls are zero. Frozen benchmarks and prior traces were not rerun or modified. Public and hidden synthetic tables are separate, and all correctness/leakage tests passed before the matrix.

Completion: 149/149 canonical settings, 14850 shared-seed synthetic instances, 133650 synthetic policy runs, and 8100 semi-synthetic policy runs. All seven vectorized/brute-force reference probes pass exactly.

## Mechanism effects in moderate-signal regimes

- P1−P0 saturation AUC effect: `0.046874`.
- P2−P1 exploration AUC effect: `-0.111195`.
- P3-generative−P2 counterfactual AUC effect: `0.001368`.
- P3-generative−P3-frozen calibration gap: `-0.000045`.

All effects are paired over shared instances/seeds; cell-level confidence intervals and negative regimes are preserved in `analysis/paired_effects.csv` and `analysis/MECHANISM_PHASE_DIAGRAMS.csv`.

## Semi-synthetic representation dependence

- H1 public representation counterfactual gain: `0.000927`.
- evaluator-derived event-aligned representation gain: `-0.000030`.
- H1 public representation saturation gain: `-0.003978`.
- evaluator-derived event-aligned saturation gain: `0.025434`.

This sign reversal is the main competing explanation to a general saturation claim: P1 works in controlled/event-aligned regimes but does not transfer to the frozen H1 public representation.

## Suite-level results

| suite            |   Delta_calibration |   Delta_counterfactual |   Delta_exploration |   Delta_saturation |
|:-----------------|--------------------:|-----------------------:|--------------------:|-------------------:|
| A_SATURATION     |        -0.000215305 |            0.00042178  |          -0.171937  |          0.0936993 |
| B_COUNTERFACTUAL |         0.000218724 |            0.00791033  |          -0.110629  |          0         |
| C_ROBUSTNESS     |         3.03204e-05 |            0.000459644 |          -0.138092  |          0.0220012 |
| C_SCALE          |         5.22205e-05 |            0.000643807 |          -0.100145  |          0.0150646 |
| D_EXPLORATION    |         0.000350673 |            0.00248183  |          -0.0927866 |          0.0162575 |

Suite B's nominal `merge_ambiguity`/barrier-frequency axis is invalid as a causal sweep: the parameter is not consumed by the generator, and all three nominal levels are identical per seed. Its apparent counterfactual effect cannot establish barrier-frequency robustness.

## N=1000 scale check

|    n | comparison           |   mean_effect |     ci95_low |    ci95_high |   seeds |
|-----:|:---------------------|--------------:|-------------:|-------------:|--------:|
|  120 | Delta_calibration    |   0.000183983 | -0.000181079 |  0.000549044 |     100 |
|  120 | Delta_counterfactual |   0.000805594 |  0.000155917 |  0.00145527  |     100 |
|  120 | Delta_exploration    |  -0.105838    | -0.113807    | -0.097869    |     100 |
|  120 | Delta_saturation     |   0.0204137   |  0.0161649   |  0.0246625   |     100 |
|  347 | Delta_calibration    |  -0.000326842 | -0.000699209 |  4.5526e-05  |     100 |
|  347 | Delta_counterfactual |   0.000833578 |  0.000344003 |  0.00132315  |     100 |
|  347 | Delta_exploration    |  -0.0929433   | -0.0982612   | -0.0876253   |     100 |
|  347 | Delta_saturation     |   0.0162318   |  0.013822    |  0.0186415   |     100 |
| 1000 | Delta_calibration    |   0.00029952  | -0.000122745 |  0.000721786 |      50 |
| 1000 | Delta_counterfactual |   0.00029225  | -0.000119205 |  0.000703704 |      50 |
| 1000 | Delta_exploration    |  -0.101653    | -0.109337    | -0.09397     |      50 |
| 1000 | Delta_saturation     |   0.00854829  |  0.00585138  |  0.0112452   |      50 |

## Thresholds and decision

Minimum stable saturation AUROC: `0.55`. Minimum stable counterfactual AUROC: `0.55`. Minimum candidate recall in qualifying counterfactual cells: `0.6`.

The strongest supported conclusion is `IDEAL_SIGNAL_ONLY`: synthetic and event-aligned evidence supports saturation, while exploration is strongly harmful and P3 adds only about one thousandth AUC with no stable S1 gain. `IMPLEMENTATION_CALIBRATION_GAP = false`.

`REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = false`. Controlled signal thresholds are not promoted to engineering targets because H1 saturation reverses sign and the Suite B manipulation failed. Exact next action: stop planner/cheap-primitive engineering; retain EventRelation + BB-EM/operator route.
