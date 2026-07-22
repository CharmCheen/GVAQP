# Minimal Physical PSVR Smoke Test

`PSVR_PHYSICAL_SMOKE_TEST = FAIL`

This six-case guard test used a resident physical Qwen3-VL-32B oracle and an unmaterialized physical YOLO proxy. Oracle initialization (155.475 s) is outside Regime-B deadlines. Cache replay calls: 0.

Deadlines: T_short=30.778 s, T_mid=76.373 s, T_long=122.968 s.

After this smoke run, the Regime-B proxy operators were re-frozen with Qwen resident on the same GPU. The final recommended deadlines are 30.830 / 76.891 / 123.952 s; the largest shift is 0.984 s. This does not change the verdict: Coverage-Interleave T_short ended at 35.664 s, still 4.834 s beyond the final T_short.

Checks: {"all_deadlines_met": false, "all_six_cases_present": true, "boundary_state_is_censored": true, "coverage_no_future_proxy_access": true, "incomplete_proxy_physically_observed": true, "k3_snapshot_committed_before_deadline": false, "physical_oracle_latency_counted": true, "positive_k3_path_exercised": true, "strict_results_confirmed_only": true}

This is not a quality comparison. K3 and reference semantics are unchanged; outputs are strict confirmed-only with unit-interval-censored boundary state.

The decisive failure is physical tail latency: the T_short run started VERIFY under the p95 guard, but that invocation took 21.436 s and the durable commit missed its deadline. The sample is retained rather than replaced.
