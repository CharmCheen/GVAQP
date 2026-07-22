# H-STAGE1 observable stage-conditioned controller

`BRANCH_DECISION = REJECT_NO_CROSS_VIDEO_QUALITY_SIGNAL`

`PHYSICAL_VALIDITY_GATE = PASS`

`PREREGISTERED_CORRECTNESS_GATE = FAIL_EXACT_REPEAT_SIGNATURE`

`CROSS_VIDEO_QUALITY_SIGNAL = False`

`KEY_ABLATION_OR_REVISION = NOT_RUN_BRANCH_REJECTED`

`PSVR_TWO_VIDEO_SEARCH = NO_GO`

ST1 converted unused deadline into substantially more SCAN and VERIFY actions and consistently
recovered a second event on V0_Q2. It recovered no event on either V1 task in any of twelve
physical cells, despite evaluator-only evidence that positive units were scanned. Therefore the
mechanism improves exposure but not cross-video candidate-to-VERIFY/event conversion. This is not
a near miss under the frozen rule: the required cross-video direction is absent, so neither an
ablation nor the single causal revision is triggered.
