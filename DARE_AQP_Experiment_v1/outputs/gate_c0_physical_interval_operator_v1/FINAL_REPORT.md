# Physical interval-operator Gate v1

## Decision

**`INTERVAL_OPERATOR_CONTRACT_BLOCKED`.** No physical VLM call was made.

The frozen C0 semantics and cost gate were recovered, but the numerical
physical-accuracy thresholds required by the authorized task do not exist in
the governing C0 artifacts. In particular, ANY pruning safety and COUNT
undercount have no registered acceptance limits. Because the task explicitly
forbids changing thresholds after inference and mandates this stop label when
decision thresholds cannot be recovered, executing the 160-call matrix would
produce measurements that could not support a compliant primary decision.

## Direct evidence

- GPU was usable: NVIDIA A100-SXM4-80GB, 81,153 MiB free at recovery.
- Exact strict model was present: Qwen3-VL-32B-Instruct, full content hash
  `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`.
- No duplicate interval process or `interval_oracle_gate_v1` tmux session existed.
- New physical calls: **0/160**.
- The prior exact C0 result remains `CONDITIONAL_C0_ONLY`; it is neither upgraded
  nor rejected by this blocked recovery.

## Why inference was not informative yet

Accuracy numbers alone cannot determine GO, and cost alone cannot determine GO.
Without preregistered limits for ANY false negatives and COUNT undercount, the
same observed matrix could be declared passing or failing after the fact. That
is precisely the decision leakage the frozen-gate design is intended to prevent.

## Next action

Create a protocol-only amendment—without viewing any new interval responses—that
sets numerical ANY sensitivity/specificity/false-negative, COUNT exact/MAE/
undercount, multi-event and abstention gates. Then rerun contract recovery. The
sample, prompts and physical call matrix remain uncreated and therefore unspent.
