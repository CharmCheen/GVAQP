# Final Summary

- Timestamp: 2026-06-27T15:21:58Z
- Task type: pure analysis; no large model was run.
- Decision: `WEAK_GO_MIXED_CERTIFICATE_POWER`.
- Dataset3 positive R_lower gap budgets: 3/7, mean gap 0.008280.
- Realcartest positive R_lower gap budgets: 0/7, mean gap -0.041468.
- Core result: Strategy7 improves L3-missed positive recovery but does not reliably tighten the exact hypergeometric recall lower bound under the current 70/20/10 split.
- Dataset3 certificate gain appears in mid budgets; realcartest certificate lower bounds are worse for Strategy7 at every tested budget.
- Certificate validity boundary: only uniform random audit contributes to the hypergeometric residual bound.
- See `reports/STRATEGY7_CERTIFICATE_POWER_REPORT.md` for full tables and limitations.

strategy7_certificate_power_complete=true
