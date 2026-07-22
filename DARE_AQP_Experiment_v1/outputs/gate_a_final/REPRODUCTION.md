# Gate A reproduction

From `/qiuyeqing/llama_prl/G-ARC`:

```bash
/qiuyeqing/tools/miniconda3/envs/garc/bin/python DARE_AQP_Experiment_v1/scripts/acquire_gate_a_models.py
/qiuyeqing/tools/miniconda3/envs/garc/bin/python DARE_AQP_Experiment_v1/scripts/run_gate_a_inference.py --device cuda --execute --output DARE_AQP_Experiment_v1/outputs/gate_a_final
/qiuyeqing/tools/miniconda3/envs/garc/bin/python DARE_AQP_Experiment_v1/scripts/finalize_gate_a.py
/qiuyeqing/tools/miniconda3/envs/garc/bin/python DARE_AQP_Experiment_v1/scripts/audit_gate_a.py
python -m unittest discover -s DARE_AQP_Experiment_v1/tests -v
```

The inference command resumes from valid per-unit checkpoints. To reproduce a
true cold construction ledger rather than validate the sealed run, use a new
output directory; do not delete the sealed artifacts.
