# Deadline semantics

Admission is `estimated_complete_cost <= remaining_budget` for finite non-negative values. SCAN and CONFIRM are indivisible complete actions. STOP is returned when neither legal action fits; CONFIRM is additionally illegal on an empty Frontier. If exactly one legal action fits, it is selected regardless of the current ratio target.

The frozen replay uses a global measured cost fallback until an action type has completed, then the linear-interpolated q90 of causally observed costs. An admitted action can overrun if actual cost exceeds its estimate. Such an action remains a complete, durably recorded action, but utility-at-deadline excludes its late result. A failed action may consume reported elapsed time but is not recorded as complete and does not update the 25:75 ratio. Therefore `physical_hard_deadline_safety = NOT_ESTABLISHED`; this repository does not relabel predictive admission as a hard guarantee.
