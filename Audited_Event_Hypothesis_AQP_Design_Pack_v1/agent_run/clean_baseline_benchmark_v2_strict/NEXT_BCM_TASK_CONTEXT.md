# NEXT BCM TASK CONTEXT

- Strict benchmark ID: `cbbv2_514c0d360fd5b2a4b5fe`
- Strict oracle-build ID: `strict_oracle_3b9ba1187c0449426978`
- Public planner inputs: `frozen_inputs/units.csv`, `frozen_inputs/public_proxy.csv`
- Evaluator-only/forbidden online: `frozen_inputs/oracle_observations.csv`, `frozen_inputs/event_reference.csv`, `oracle/parsed/`, `evaluator/`, saved matches/metrics
- OracleAccessor: `scripts/run_clean_benchmark_v2_strict.py::OracleAccessor`
- Materializers/evaluator: `scripts/benchmark_lib.py::{materialize_from_trace,evaluate_events}`
- Matcher: overlap-any one-to-one, maximum cardinality then temporal IoU; hash in `BENCHMARK_MANIFEST.json`
- Budgets: `[5, 10, 20, 50, 80, 100]`; one logical cost per unique query; duplicates rejected
- Expected matrix: 1,464 baseline + 12 MAP/M1 runs
- Best native: `B5_ARC_native/arc_refinement_th0.4_native` AUC `0.389659`
- Best controlled: `B1_top_proxy/top_proxy_controlled_bridge_safe` AUC `0.354212`
- Required BCM output: `agent_run/bcm_aqp_experiment_v2`
- No BCM physical VLM calls; never modify this strict directory after freeze.
