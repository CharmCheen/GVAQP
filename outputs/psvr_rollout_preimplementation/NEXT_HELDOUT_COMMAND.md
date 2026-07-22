# Held-out command (not authorized and not executed)

```bash
python scripts/run_psvr_rollout_h1a_heldout.py --preregistration outputs/psvr_rollout_preimplementation/UPDATED_H_ROLLOUT1A_PREREGISTRATION.json --confirm-heldout
```

The current preregistration makes this command fail closed before the held-out
seed file is opened. It may be authorized only after a result-blind D3/D4
consistency revision, full tests, development smoke, re-freeze, and review.

