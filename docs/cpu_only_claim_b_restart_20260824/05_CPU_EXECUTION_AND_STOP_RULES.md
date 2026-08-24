# B0 CPU execution and stop rules

## Required checks

1. Parse both canonical CSV ledgers.
2. Run focused B0 contract tests.
3. Run legacy causal-frontier tests to detect regression.
4. Inspect policy-visible schema for forbidden reference/truth/oracle fields.
5. Compile the new module.
6. Freeze hashes only after all checks pass.

## PASS

All eight criteria in `NEXT_STAGE_STATE_MACHINE.md` pass, exact parity holds,
and the manifest records the exact files. Report only
`B0_CPU_INFRASTRUCTURE_QUALIFIED`.

## FAIL

Any invariant, schema, compilation, or parity failure yields
`B0_CPU_CONTRACT_FAIL`. Do not repair by adding hidden candidates, reference
features, policy-specific evaluation, or an uncharged operation.

## Authorization after PASS

PASS permits drafting a fresh-workload/physical-cost protocol. It does not
permit running it, collecting human work, calling a model, or training a
controller without new explicit authorization.
