# Myopic-VPS

- Original hypothesis: causal marginal value-per-second estimates could outperform fixed allocation.
- Scope: two videos, four query groups, measured-action trace replay.
- Main metrics: primary utility AUC delta -187.5; low-budget delta -0.5; nonnegative cross-group rate 0.25; leave-best-group-out -250.
- Result/failure mechanism: estimated action values did not generalize across the sparse groups; the selected prior/configuration underperformed fixed R4.
- Failed Gate: preregistered controller benefit tests.
- Current disposition: signal not established; Myopic implementation excluded; R4 retained.
- Source: `outputs/scan_confirm_decision_v1/reports/FINAL_DECISION.md`, commit `5047241b0561b911b9a519b18e8e7591c0074e70`.
