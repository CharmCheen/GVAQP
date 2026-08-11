# Reproduction

All commands are CPU-only unless explicitly described otherwise.

```bash
cd /root/charm/GVAQP_side_rcsem
PYTHONPATH=src:experiments pytest -q
PYTHONPATH=src python -m compileall -q src experiments tests
PYTHONPATH=src:experiments python experiments/controller_dynamic_headroom.py \
  --arc-root /root/charm/GVAQP-arc-phys-baseline \
  --output outputs/controller_dynamic_headroom_cached_v1_reproduction
PYTHONPATH=src:experiments python experiments/public_state_predictability.py \
  --branches outputs/controller_dynamic_headroom_cached_v1_reproduction/STATE_ACTION_BRANCHES.jsonl \
  --output outputs/public_state_predictability_cached_v1_reproduction
```

The branch program refuses to overwrite its output directory. Compare the
reproduction `SUMMARY.json` and `STATE_ACTION_BRANCHES.jsonl` hashes to the run
manifest rather than replacing this exploration directory.

Do not run V3 downstream commands until the formal full-grid release contains
1,475 authenticated terminal records, finalizer PASS, released K3 relation,
reference manifest, and an explicit downstream release commit. No large GPU
experiment is authorized by this reproduction note.
