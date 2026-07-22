# Exact commands

```bash
cd /qiuyeqing/llama_prl/G-ARC
python scripts/audit_psvr_recoverability.py
python scripts/evaluate_psvr_bottleneck.py h-bottle2
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_psvr_stage1_physical.py check
python scripts/freeze_psvr_two_video_deadlines.py profile
python scripts/run_psvr_stage1_physical.py smoke
python scripts/run_psvr_stage1_physical.py smoke-gate
python scripts/run_psvr_stage1_physical.py formal
python scripts/evaluate_psvr_stage1.py
```

The profile command refreshed expired observations only. The deadline `freeze` subcommand was not
run. Invalid pre-gate attempts and prior profiles are retained in the two cycle-specific invalidation
directories and the timestamped deadline profile archive.

`NEXT_EXACT_COMMAND = NONE_TWO_VIDEO_RULE_SEARCH_TERMINAL`
