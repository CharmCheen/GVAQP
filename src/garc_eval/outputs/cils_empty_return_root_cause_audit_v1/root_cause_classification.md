# Root Cause Classification

Primary root cause: **CALIBRATION_FLOOR_TOO_LOW / PRECISION_CONSTRAINT_IMPOSSIBLE, caused by weak top-score pilot positives**.

Secondary root causes:

- **PILOT_SPARSITY / weak positive pilot yield**: top-score CILS pilots contain no answer-positive intervals at B=5/10/20 and low positive rates at B=40/80.
- **SCORE_RANKING_FAILURE**: answer-positive candidates exist, but high active-score prefixes have low answer-positive yield.
- **REFERENCE_MIXTURE_EFFECT**: point-anchor events make the global answer target brittle, though this audit focuses on interval-eval events.

Not supported as primary causes:

- **SELECTOR_IMPLEMENTATION_BUG**: oracle `p_answer` counterfactual returns intervals.
- **UTILITY_OR_DURATION_PENALTY_SUPPRESSES_SELECTION**: utility remains positive; candidates are rejected by expected precision before duration penalty dominates.
- **OVERLAP_CONTROL_SUPPRESSES_SELECTION**: no selected spans are established before precision rejection.

Key evidence:

| root_cause | support | evidence |
| --- | --- | --- |
| PILOT_NO_POSITIVES | budget_dependent_not_primary | B=5: zero_rate=1.000, pos_rate=0.000; B=10: zero_rate=1.000, pos_rate=0.000; B=20: zero_rate=1.000, pos_rate=0.000; B=40: zero_rate=0.000, pos_rate=0.050; B=80: zero_rate=0.000, pos_rate=0.100. B=80 has positives, so no-positive pilot alone cannot explain empty return. |
| CALIBRATION_FLOOR_TOO_LOW | strong | B=80 mean max p_answer=0.214, below tau_p grid minimum 0.5 |
| PRECISION_CONSTRAINT_IMPOSSIBLE | strong | first selected candidate must satisfy p_answer >= tau; clean calibrated p_answer max is below tau=0.5 |
| SELECTOR_IMPLEMENTATION_BUG | not_supported | oracle p_answer B=80 tau=0.5 return_rate=1.000 |
| UTILITY_OR_DURATION_PENALTY_SUPPRESSES_SELECTION | not_primary | positive utility exists; rejection happens before utility can matter because expected precision fails |
| OVERLAP_CONTROL_SUPPRESSES_SELECTION | not_primary | no selected spans exist before precision rejection; overlap conflicts are not the first blocker |
| SCORE_RANKING_FAILURE | secondary | top_score pilot positive rates are low despite many answer-positive candidates |
| REFERENCE_MIXTURE_EFFECT | secondary | point/interval mixture affects global target, but interval positives are still assigned low p_answer under top-score pilot |

Top rejection reasons for B=80, tau=0.5:

| budget | tau | rejection_reason | count | total | fraction |
| --- | --- | --- | --- | --- | --- |
| 80 | 0.5 | p_answer_too_low | 240000 | 240000 | 1 |

Conclusion: CILS empty return is real and is caused by calibrated `p_answer` never reaching the requested `tau_p` threshold. The selector requires the first added interval to satisfy expected precision, so with `max(p_answer) < 0.5`, every candidate is rejected at tau=0.5 and above.
