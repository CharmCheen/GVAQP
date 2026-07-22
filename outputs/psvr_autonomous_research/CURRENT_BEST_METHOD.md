# Current best PSVR method

`CURRENT_BEST_SIMPLE_BASELINE = FIFO`

`CURRENT_BEST_VALIDATED_CORE_METHOD = NONE`

`BEST_OBSERVED_REJECTED_CONFIGURATION = ST1`

ST1 has the highest descriptive macro AUC in the final branch matrix (0.047547) and recovers one
additional V0_Q2 event, but it is not a method candidate: it wins only one task on one video,
recovers zero V1 events in 12/12 cells, fails all substantive thresholds, and fails the stricter
exact-repeat signature condition. FIFO remains the best simple baseline; no method is usable or
frozen for generalization.

`PSVR_TWO_VIDEO_SEARCH = NO_GO`
