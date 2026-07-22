# Exact commands

```bash
cd /qiuyeqing/llama_prl/G-ARC
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_psvr_stage4_scan_ablation.py
python scripts/evaluate_psvr_stage4_scan_ablation.py
PYTHONPATH=src pytest -q tests/psvr_runtime
```
