# Reproduction

All commands run from `/qiuyeqing/llama_prl/G-ARC`.

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict
python "$PACK/scripts/build_strict_oracle.py" --stage verify
python "$PACK/scripts/run_clean_benchmark_v2_strict.py" --stage all
python "$PACK/scripts/validate_benchmark_compatibility.py" --new-manifest "$PACK/BENCHMARK_MANIFEST.json" --new-run-id self_check
```

The oracle builder resumes only exact raw outputs from the same oracle-build ID;
it never imports legacy responses. Valid completed baseline runs are reused only
when their manifests and artifact hashes verify; incomplete runs are preserved
outside the aggregation tree and rerun cleanly. No BCM run may make a physical
VLM call.
