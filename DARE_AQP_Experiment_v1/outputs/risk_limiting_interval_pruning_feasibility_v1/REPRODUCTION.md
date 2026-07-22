# Reproduction

```bash
python garc_eval/risk_limiting_interval_v1/simulate.py
python garc_eval/risk_limiting_interval_v1/summarize.py
python garc_eval/risk_limiting_interval_v1/audit.py
```

The simulator is reference-only and must not load a VLM or physical response.
Each stochastic cell uses 500 seeds. Runtime on the current host was dominated
by the full estimator/error grid.
