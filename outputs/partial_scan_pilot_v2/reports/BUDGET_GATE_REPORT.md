# V2 Budget Gate Report

```text
SCHEDULER_OVERHEAD_INCLUDED_IN_DEADLINE = true
remaining_budget_at_validation_sec = remaining_budget_before_step_sec
  - policy_request_serialize_sec - IPC - policy_decision_sec
  - policy_response_validation_sec - environment_action_validation_sec
ACTION_START = estimated_post_validation_completion_sec
  <= remaining_budget_at_validation_sec
```

The shared application accounting helper is used by Replay and Physical paths.
The validation value is an admission calculation only; actual scheduler time is
charged once to the run ledger after execute or reject, avoiding duplicate
scheduler-overhead deduction. A started microchunk is not aborted.

Constructed timing tests passed for estimate less than, equal to, and greater
than remaining budget; zero and negative remaining budget; and actual cost both
below and above the estimate.

`BUDGET_GATE_CORRECTNESS = PASS`
