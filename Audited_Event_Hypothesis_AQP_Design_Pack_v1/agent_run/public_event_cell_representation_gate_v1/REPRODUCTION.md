# Reproduction

```bash
PYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate run
PYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate seal
```

The first command refuses to overwrite an existing completed run. The seal command requires a passing independent review JSON and revalidates all final hashes.
