# M0 Shared Execution Status

## Verdict

`M0_PASS_FOR_CPU_REPLAY_CONTRACT`

## Tested command

```bash
PYTHONPATH=src python3 -m pytest tests/test_causal_frontier.py -q
```

## Result

`15 passed in 0.06s`

The passing suite covers causal candidate visibility, fallback retention,
structured 0-N verification output, track-and-gap materialization, deadline
immutability, order-specific SCAN cost, fixed 10-second VERIFY windows, exact
identity-trace evaluator parity, fixed uniform-stride order, fallback deferral,
cost-ratio-sensitive DATB interleaving, and causal SCAN-then-VERIFY routing for
the ExSample adaptation.
Cached oracle failures are also charged and surfaced explicitly rather than
coerced into negative labels.

## Scope limit

This verdict validates the shared CPU execution contract only. It is not evidence
that DATB-SV outperforms a baseline. `T2` still requires a causal existing-corpus
adapter and `ExSample-EndToEnd` before claim-grade comparison.
