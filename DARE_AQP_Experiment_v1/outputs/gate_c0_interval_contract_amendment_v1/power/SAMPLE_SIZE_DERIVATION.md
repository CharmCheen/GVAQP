# Exact sample-size derivation

The critical estimands are effective ANY sensitivity and specificity after all
confidence, abstain, parser and completeness mappings. A one-sided 95% exact
Clopper–Pearson lower bound is frozen. With `n` successes in `n` independent
trials, the lower bound is `0.05^(1/n)`.

The conservative feasible region requires sensitivity 1.00 and specificity
0.99 with zero UNKNOWN. No finite binomial sample can have a lower confidence
bound of 1.00. Even substituting 0.99 only for the power calculation—not as a
gate—requires 299 independent positive intervals after zero false negatives;
specificity 0.99 independently requires 299 empty intervals after zero false
positives.

The proposed 160-call cap can hold 96 primary semantic intervals, 24 matched
ANY calls on the same intervals, 12 deterministic repeats, 16 unit timing calls
and 12 retry reserve calls. With at most 64 positive and 32 empty independent
primary intervals, the best zero-error bounds are 0.95427 and 0.91063. Repeats
and timing calls do not add independent semantic intervals.

Therefore the frozen threshold cannot be adjudicated within 160 calls. It is
not weakened to fit the budget.
