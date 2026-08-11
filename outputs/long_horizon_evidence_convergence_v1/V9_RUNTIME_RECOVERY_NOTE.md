# V9 Runtime-Recovery Note

`V9` is a new prospective execution recovery, not a recovery or reuse of the
incomplete V7/V8 labels. It was frozen before V9 model inference and runs the
same V3 semantic model, processor, prompt, query, unit grid, decoding, parser,
reference semantics, and sealed GPU pairs as V7.

V7 is preserved as `FULL_GRID_ABORTED_RUNTIME` with 1,385 terminal records and
no formal publication. V8 is preserved as a zero-unit harness abort: the V7
CLI had been captured as a Python default spawn argument. V9 explicitly binds
the recovery worker callback, retains the no-reuse/fresh-from-unit-zero rule,
and records the 35-second call reservation/30.4 A100-hour recovery cap from
V7 runtime-only timings. No semantic raw response, reference relation,
selector result, K0/K3 result, or Event-F1 value was read to choose V9.

V9 seal:
`57538d23ecfce5df23c58ba471e7efce206df4fb60f1dd226b549773e4233f9e`.
