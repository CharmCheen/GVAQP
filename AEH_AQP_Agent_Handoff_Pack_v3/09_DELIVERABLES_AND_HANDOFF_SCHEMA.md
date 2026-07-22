# Deliverables and Handoff Schema

Every new experiment must use a new directory:

```text
agent_run/<experiment_name>_vN/
├── FINAL_REPORT.md
├── FINAL_DECISION.csv
├── EXPERIMENT_MANIFEST.json
├── FILE_MANIFEST.csv
├── REPRODUCTION.md
├── config/
├── inputs/
├── runs/
├── aggregates/
├── diagnostics/
├── logs/
└── audit/
    ├── COMPLETION_AUDIT.csv
    └── INDEPENDENT_ADVERSARIAL_REVIEW.json
```

## `FINAL_DECISION.csv`

At minimum:

```text
experiment_id
decision
benchmark_id
formal_runs_expected
formal_runs_completed
physical_vlm_calls
logical_oracle_calls
completion_audit
independent_review
primary_metric
best_method
best_baseline
claim_impact
next_action
```

## `EXPERIMENT_MANIFEST.json`

At minimum:

- experiment/benchmark/oracle IDs;
- parent artifacts and hashes;
- Git commit/status;
- source/config/input hashes;
- expected matrix and seeds;
- immutable paths;
- command ledger;
- hardware/packages;
- start/end time;
- logical/physical calls;
- skipped phases and reasons;
- final decision and gate version.

## `FINAL_REPORT.md`

Required sections:

1. decision and one-paragraph meaning;
2. research question and pre-registered gate;
3. frozen inputs and leakage boundary;
4. methods and exact differences;
5. completion/accounting;
6. primary results with uncertainty;
7. action/trace activation;
8. causal failure or success decomposition;
9. limitations/non-claims;
10. paper-claim impact;
11. exact next experiment.

## Independent review

It must recompute key metrics from primitive artifacts, verify matrix/accounting/leakage/hashes and challenge the decision against the frozen gate. It must not merely reread `FINAL_REPORT.md`.

## Final handoff message

Use `templates/FINAL_HANDOFF_TEMPLATE.md`. The next agent must be able to continue using only that message, this pack and the server artifacts.

