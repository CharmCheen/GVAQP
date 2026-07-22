# Reproduction

All commands run from `/qiuyeqing/llama_prl/G-ARC`.

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1
python "$PACK/scripts/run_clean_benchmark.py" --stage all
python "$PACK/scripts/validate_benchmark_compatibility.py" --new-manifest "$PACK/BENCHMARK_MANIFEST.json" --new-run-id self_check
```

The pack is immutable. The command refuses to overwrite nonempty run directories; create `clean_baseline_benchmark_v1_run2` for a fresh rerun.

Raw-cache reuse requires the exact video SHA256, interval, model/config manifest hash, prompt hash, parser hash, and an extant raw response. Logical queries are charged even on physical cache hits.
