# Reproduction

Run from `/qiuyeqing/llama_prl/G-ARC` in the existing `garc` environment.
These commands make no model-generation call and do not modify prior sprint
artifacts.

```bash
export PYTHONPATH=src
python -m garc_eval.event_enumerate_v2.forensics
python -m garc_eval.event_enumerate_v2.generate_metadata_corpus
python -m garc_eval.event_enumerate_v2.freeze
pytest -q AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/tests   --junitxml=AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/runtime/pytest_results.xml
python -m garc_eval.event_enumerate_v2.audit_heldout
python -m garc_eval.event_enumerate_v2.preexecution_audit
python -m garc_eval.event_enumerate_v2.seal
```

Expected test result: `25 passed`; expected pre-execution result:
`15/15 PASS`.  Expected terminal decision:
`HELDOUT_DATA_REQUIRED`; `physical/attempts` must remain empty and
`physical/NO_CALLS.json` must report zero calls.

Do not run a physical command after this reproduction.  A later physical run
requires a newly supplied held-out reference, frozen evaluator-only sample,
preregistered call matrix, independent review, and an unchanged passing
processor audit.
