# Complete identity contract

Every execution identity carries `episode_id`, `configuration_id`, `method_id`, `posterior_budget_id`, `trajectory_budget_id`, `error_target`, `error_form`, `error_magnitude`, `error_direction`, `planning_cost_id`, `fallback_variant`, and `attempt_ordinal`. A canonical JSON encoding is SHA-256 hashed; absent fields, unknown error fields, and duplicate hashes fail closed.
