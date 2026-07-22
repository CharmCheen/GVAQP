# Next authorized command

Run this command exactly once, only after reviewing the E1 completion audit and
accepting irreversible creation of the new sealed confirmatory universe:

```bash
cd /qiuyeqing/llama_prl/G-ARC
PYTHONPATH=src python scripts/run_psvr_rollout_h1a_r2e1_confirmatory.py --generate-and-run-confirmatory
```

This command is intentionally not executed by the E1 amendment turn.
