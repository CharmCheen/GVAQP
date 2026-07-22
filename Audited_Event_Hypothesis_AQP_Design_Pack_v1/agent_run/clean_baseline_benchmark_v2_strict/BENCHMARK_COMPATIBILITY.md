# Benchmark Compatibility

Benchmark ID: `cbbv2_514c0d360fd5b2a4b5fe`

The ID binds semantic hashes of video, units, proxies, cheap-feature manifest, oracle model/prompt/parser, reference, budgets, evaluator, matching, and baseline code. Semantic CSV hashes exclude the `benchmark_id` column to avoid a self-referential hash; physical file hashes are recorded separately in `BENCHMARK_MANIFEST.json`.

Any change to video, units, proxy, strict oracle build, reference, budgets,
evaluator, or matching creates an incompatible benchmark. A materializer-only
change may replay saved traces; a planner-only change may use the frozen oracle
only after compatibility validation. The strict benchmark directory must not
be modified after the final freeze marker.
