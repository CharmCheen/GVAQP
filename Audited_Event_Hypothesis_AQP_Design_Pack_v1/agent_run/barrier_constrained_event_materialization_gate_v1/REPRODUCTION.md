# Reproduction

```bash
PYTHONPATH=src pytest -q Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/barrier_constrained_event_materialization_gate_v1/tests
PYTHONPATH=src python -m garc_eval.bcem_gate_v1.run_ceiling run
PYTHONPATH=src python -m garc_eval.bcem_gate_v1.run_public
PYTHONPATH=src python -m garc_eval.bcem_gate_v1.finalize prepare
PYTHONPATH=src python -m garc_eval.bcem_gate_v1.finalize seal
```

All acquisition inputs are saved traces. The ceiling command is evaluator-only; the public module has no reference input.
