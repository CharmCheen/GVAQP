# Exact commands

```bash
cd /qiuyeqing/llama_prl/G-ARC
python scripts/analyze_psvr_stage3_attribution.py
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_psvr_stage3_factorization.py smoke
python scripts/run_psvr_stage3_factorization.py matrix
python scripts/run_psvr_stage3_factorization.py finalize
python scripts/audit_psvr_stage3_results.py
PYTHONPATH=src pytest -q tests/psvr_runtime
```

The first smoke invocation produced a retained pre-runtime identity-schema failure and zero physical calls. After correcting the manifest transcription before the first physical run, the smoke command was rerun. The four valid smoke runs plus 36 matrix runs exactly consumed the physical cap of 40.
