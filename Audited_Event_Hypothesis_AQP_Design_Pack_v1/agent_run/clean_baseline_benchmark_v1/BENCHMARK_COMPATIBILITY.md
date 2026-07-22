# Benchmark Compatibility

Benchmark ID: `cbbv1_c2e246d1504d9d8a80b2`

The ID binds semantic hashes of video, units, proxies, cheap-feature manifest, oracle model/prompt/parser, reference, budgets, evaluator, matching, and baseline code. Semantic CSV hashes exclude the `benchmark_id` column to avoid a self-referential hash; physical file hashes are recorded separately in `BENCHMARK_MANIFEST.json`.

Any change to video, units, proxy, oracle model/prompt, reference, budgets, evaluator, or matching is incompatible with direct v1 comparison and requires benchmark v2 or an explicitly narrower compatibility statement. A materializer-only change may replay saved traces. A planner-only change may reuse frozen baseline results when compatibility validation passes. A new human GT reference may reevaluate saved event segments without acquisition/VLM reruns but creates a new reference/evaluator/comparison version.
