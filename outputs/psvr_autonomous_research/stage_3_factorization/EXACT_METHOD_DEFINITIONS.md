# H-FACT1 exact method definitions

All cells use the same physical operators, candidate rule, tie-break, K3 materializer, deadline guard, checkpoints, and A800 runtime identity frozen in `DEV_TASK_MANIFEST.json`.

`S0` returns the next four unobserved members of the fixed list `range(1, 347, 3)`. `S1` is byte-for-behavior equivalent to the Stage-2 Coverage-Debt batch rule with lambda 0.5 and beta 0.25; only physically observed proxy scores enter its local-signal term.

`A0` is the fixed Stage-2 Coverage-Interleave allocation schedule: 29 SCAN epochs, covering all 116 coarse-grid cells in batches of four (the final batch has four because 1..346 step 3 contains 116 cells), followed by VERIFY at every decision epoch while candidates remain. The allocation is not changed by proxy values. For `C1`, the same fixed 29-SCAN/then-VERIFY schedule is used with S1 batches.

`A1` is the Stage-2 state-dependent rule: SCAN if no candidate exists or `scan_actions <= completed_VERIFY_actions`, otherwise VERIFY. Thus it normally alternates one SCAN batch and one VERIFY, but its definition includes empty/exhausted states.

- `C0 = S0 + A0` (behavior-equivalent to Stage-2 `coverage_interleave`).
- `C1 = S1 + A0`.
- `C2 = S0 + A1`.
- `C3 = S1 + A1` (behavior-equivalent to Stage-2 `coverage_debt_psvr`).

VERIFY always chooses the scanned, unqueried unit with maximum observed proxy score, breaking ties by ascending unit id. The physical deadline, not an action-count quota, ends each run.
