# SCAN–CONFIRM controller

The selected controller is `R4_FIXED_TIME_RATIO_25_75`: target 25% of completed realized action time for SCAN and 75% for CONFIRM. It is not an action-count ratio. First action is SCAN because the Frontier is empty and elapsed action time is zero.

After every complete action the controller observes actual cost. Incomplete actions do not update the ratio. At each boundary it independently checks whether each estimated complete action fits. Desired-action fallback, STOP, and Frontier semantics are specified in [the algorithm specification](ALGORITHM_SPEC.md).

The complete rule is: STOP if neither complete action fits; SCAN if the Frontier is empty; use the sole fitting action if only one fits; otherwise choose SCAN when the realized SCAN share is below 0.25 and CONFIRM when it is at or above 0.25. Thus unequal action costs, not action counts, determine the choice.
