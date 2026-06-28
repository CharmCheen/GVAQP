# Final Summary

- Output timestamp: 2026-06-27T14:37:38Z
- Qwen/final oracle called: NO.
- GLM called: YES.
- GLM fixed-prompt outputs: 399 anchors; parse success 398; parse_error 1.
- YOLO called: NO.
- Acceptance audit decision: `ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION`.
- Realcartest positive rate: 0.235589.
- Realcartest `object_count_mean` AUC: 0.756418.
- Realcartest L3 baseline B=20: precision=0.800000, recall=0.170213, positives=16.000.
- Strategy 7 realcartest result: mean S7-vs-uniform-audit L3-missed recovery gap=0.057524; positive budget gaps=7/7.
- Cross-video comparison conclusion: positive.
- Final decision label: `STRATEGY7_TRANSFER_CONFIRMED`.
- Final decision condition: S7 L3-missed recovery gap positive at 7/7 budgets, mean gap 0.057524, strict acceptance, GLM available.

## Limitations

- All evaluation labels are existing V13.8 Qwen3-VL-32B oracle-relative labels, not human ground truth.
- GLM is used only as a fixed-prompt auxiliary mechanism; no prompt tuning was done on realcartest.
- Strategy replay is a no-new-final-oracle simulation over 399 pre-existing labeled anchors.
- Dataset3 and realcartest differ in positive rate, proxy ranking strength, and clean-pool/full-universe definitions.

realcartest_strategy7_validation_complete=true
