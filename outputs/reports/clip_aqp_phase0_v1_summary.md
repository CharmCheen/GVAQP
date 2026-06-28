# Clip AQP Phase 0 Summary

Output directory:

`test_vlm/outputs/clip_aqp_phase0_v1`

Final report:

`test_vlm/outputs/clip_aqp_phase0_v1/reports/PHASE0_REPORT.md`

Decision:

`FINAL_DECISION: NO_GO`

Key evidence:

- Existing local data supports pseudo-event/oracle-relative analysis only; clean event boundaries are absent.
- SUPG/window-level thresholding plus stitching has clip-level guarantee violation rate above delta in the configured pseudo-event trials.
- No-repair block/event audit was conservative in this run, but the recall lower bounds were effectively vacuous and produced no certificates.
- Repair with fresh certification was skipped because B1 did not produce conservative non-vacuous lower bounds.
- Oracle stability checks found one ambiguous comparison and one unstable comparison, so no human-truth guarantee is defensible.

This is an engineering Phase 0 result over VLM-defined pseudo-oracle labels, not a human-ground-truth G-ARC guarantee.
