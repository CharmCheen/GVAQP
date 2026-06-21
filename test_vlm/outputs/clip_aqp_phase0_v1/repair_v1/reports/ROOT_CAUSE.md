# Root Cause: Phase 0 Bound Formula Defect

## Files Inspected

- `test_vlm/outputs/clip_aqp_phase0_v1/scripts/phase0_common.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/scripts/20_block_audit_simulation.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/diagnostics_v1/reports/DIAGNOSTIC_REPORT.md`

## Defect

The original certificate code computed:

```python
lcb_y = max(0.0, population_n * (mean_y - z * se_y))
ucb_m = min(lcb_y if lcb_y > 0 else inf, population_n * (mean_m + z * se_m))
```

The `min(lcb_y, ...)` cap is invalid for an upper confidence bound on missed events. It can force `UCB_M_O` below the uncorrected missed-event point estimate `M_hat_O = population_n * mean_m`. A valid upper confidence bound must not be below its own point estimate.

## Why It Happened

The code tried to enforce the logical fact that missed events cannot exceed total events, but it used the lower confidence bound on total events (`LCB_Y_O`) as the cap for missed events. A lower bound on the denominator is not a valid upper cap for the numerator. This swapped a conservative logical constraint for an anti-conservative cap.

## Fix

The repaired code computes:

- `Y_hat_O = N * mean(Y_i^O)`
- `M_hat_O = N * mean(M_i^O)`
- `LCB_Y_O = max(0, Y_hat_O - margin_y)`
- `UCB_M_O = max(M_hat_O, M_hat_O + margin_m)`

The repaired implementation does not cap `UCB_M_O` by `LCB_Y_O`. It then computes:

```text
LCB_recall^O = max(0, 1 - UCB_M_O / LCB_Y_O)
```

when `LCB_Y_O > 0`; otherwise it returns `NO_CERTIFICATE`.

## Runtime Guardrail

The repaired code uses `epsilon = 1e-9` and halts if either invariant fails:

```text
UCB_M_O >= M_hat_O - epsilon
LCB_Y_O <= Y_hat_O + epsilon
```

On violation, it writes `reports/BOUND_INVARIANT_VIOLATION.md` with the violating input/output values and exits instead of silently clipping or continuing.

## Files Changed In This Repair

The original Phase 0 scripts are left unchanged as read-only references. The repaired implementation is written under:

- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/repair_common.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/r10_fix_bound_formula.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/r20_block_audit_no_repair_v2.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/r40_identify_certification_oracle.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/r50_generate_report_v2.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/r60_git_hygiene_snapshot.py`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/scripts/run_phase0_repair.sh`
- `garc_eval/outputs/clip_aqp_phase0_repair_v1_summary.md`

Generated repair outputs are under:

- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/tables/`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/logs/`

## Expected Effect

The old near-zero LCBs may change, but the fixed returned clips still have low oracle-relative pseudo-event recall on this 29-event benchmark. Because the benchmark remains below the 30-event caveat threshold, any decision must be reported as underpowered rather than a clean GO/NO_GO.
