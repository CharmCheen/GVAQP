# Reproduction

From the repository root, inspect the exact frozen sources listed in
`config/C0_SOURCE_MANIFEST.csv`, then run:

```bash
rg -n -i 'sensitivity|specificity|false.?negative|undercount|exact.accuracy|abstain' \
  DARE_AQP_Experiment_v1/config/gate_c0.json \
  DARE_AQP_Experiment_v1/docs/GATE_C0_PROTOCOL.md \
  DARE_AQP_Experiment_v1/docs/INTERVAL_ORACLE_CONTRACT.md \
  DARE_AQP_Experiment_v1/docs/INDEPENDENT_REVIEW_C0.md \
  DARE_AQP_Experiment_v1/outputs/gate_c0/REPORT.md
```

The absence is interpreted together with the explicit statement that C0 assumes
exact operators and real accuracy is unknown. Do not run the VLM until the
accuracy contract is amended independently of physical results.
