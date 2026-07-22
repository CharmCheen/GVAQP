# Gate A leakage audit

The inference process read only `units.csv`, `adapter_units.csv`, the frozen
video, frozen query/config, and the two exact model snapshots. Its source has no
event-reference, oracle-observation, Gate B result, or evaluator path. It wrote
all 347 scores for each semantic signal, constructed the preregistered fusion,
then atomically wrote and hashed every ranking.

The post-seal evaluator first recomputed rankings from `raw_scores.csv` using
Python's exact float parsing and verified each ranking SHA. An initial audit
attempt rejected the fusion ranking because pandas' CSV parser collapsed tiny
floating differences among mathematically tied percentile means; this happened
before labels were opened. The audit was corrected to use the same standard
`float()` parsing as the frozen evaluator and runner, after which exact order and
hash verification passed. No scores, fusion weights, or rankings changed.

Only after that seal did `evaluate_gate_a.py` join `event_reference.csv` and the
supplemental frozen K3-safe replay read cached oracle observations. Physical
exact-oracle VLM calls were zero. Verdict: **PASS**.
