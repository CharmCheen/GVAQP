# Selected-Frontier calibration

- Original hypothesis: conversion calibration on independently selected Frontiers could support Ratio-Anchored control.
- Scope: required four new mutually independent complete videos, minimum 1,200 seconds each.
- Main metric: one preliminary eligible new source; three additional sources missing; zero newly selected candidates.
- Result/failure mechanism: input availability, not a negative calibration result. Same-content/derivative/incomplete/short sources could not satisfy independence and duration.
- Failed Gate: `BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS`; dataset and C0-C4 were not built/run; new Oracle calls were zero.
- Current disposition: calibration and Ratio-Anchored controller blocked. Technical input-unlock tooling remains as research support.
- Source: `outputs/selected_frontier_conversion_v1/reports/FINAL_DECISION.md` and `input_unblock/input_gate_decision.json`, commit `5047241b0561b911b9a519b18e8e7591c0074e70`.
