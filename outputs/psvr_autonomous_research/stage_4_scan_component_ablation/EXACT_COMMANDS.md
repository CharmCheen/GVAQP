# Exact commands

```bash
cd /qiuyeqing/llama_prl/G-ARC
PYTHONPATH=src pytest -q tests/psvr_runtime
PYTHONPATH=src python scripts/verify_psvr_hscan1a.py
python scripts/run_psvr_hscan1a.py smoke
PYTHONPATH=src python scripts/verify_psvr_hscan1a.py
python scripts/run_psvr_hscan1a.py matrix
python scripts/evaluate_psvr_hscan1a.py
PYTHONPATH=src pytest -q tests/psvr_runtime
```

Next separately authorized command:

```bash
python scripts/preregister_psvr_hscan1b.py
```
