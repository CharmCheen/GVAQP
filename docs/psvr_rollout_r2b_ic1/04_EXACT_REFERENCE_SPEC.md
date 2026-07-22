# Evaluator-only exact reference

`ExactReferenceEvaluator` wraps the frozen finite-support R2 posterior and conditional rollout with shielded pi0 continuation. Its cache key is visible-history hash, remaining horizon, safe action set, and kernel hash. It is not imported by the approximate planner and cannot enter action selection.
