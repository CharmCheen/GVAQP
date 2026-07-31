# Public-state predictability report

Decision: **FAIL CACHED GATE 2; use a fixed policy**.

The 108 paired branch states were evaluated with leave-one-source-out folds.
Features were limited to elapsed/remaining budget, coverage, frontier size and
scores, committed-event count, and SCAN/VERIFY counts/balance. Reference
events and branch outcomes were targets only.

Always `VERIFY` was the best feasible rule: macro decision regret 0.000885 and
weighted sign accuracy 0.814. The best fixed-ratio probability had regret
0.003022. Every learned method was worse. Linear regression was best among
learned methods at regret 0.009693 and weighted sign accuracy 0.558, or 10.95
times the regret of always `VERIFY`. Logistic regression, histogram gradient
boosting, an 8-unit MLP, and a two-reward ridge contextual bandit likewise
failed to beat the fixed action. ID-only and shuffled-state controls were near
chance, while the evaluator-only oracle upper bound had zero regret.

LightGBM was not installed, so sklearn histogram gradient boosting is included
as the available tree-model control and the omission is explicit. With only
two independent sources, this result is exploratory; nevertheless it directly
contradicts promotion of the current public state/model family. A V3 repeat is
warranted only after the released reference and measured action costs alter
the state/Q distribution.
