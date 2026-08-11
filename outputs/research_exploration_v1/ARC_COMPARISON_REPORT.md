# ARC comparison report

Decision: **evidence insufficient** for a full-system advantage.

On exact cached inputs and logical VERIFY budgets, RC-SEM/raw-proxy ordering
had primary event-F1 AUC 0.354 versus ARC 0.224, but lost at budget 10. PSTR was
stronger at 0.380. Across the two-source sensitivity macro, the corresponding
values were 0.483, 0.262, and 0.518. RC-SEM emitted zero probable events and
its ranking was exactly descending raw proxy, so the observed win is verified
scheduling uplift over this ARC adaptation, not evidence for speculative
materialization or a learned controller.

The cached comparison shares inputs, K3, evaluator, and logical call caps, but
is not a native physical comparison: ARC's original CDF features and exact
instrumented entry point are missing, ARC may stop below a budget cap, and no
wall-clock path is measured. The ARC worktree is also dirty with user-owned
physical/cached adaptations. No fair V3 native-system comparison or controlled
physical SCAN/controller/VERIFY comparison exists.

The V3 full-grid has now aborted on its sealed cost bound, so a physical common
reference/runtime comparison is not merely pending; it is unavailable under
the current experiment and approval. The strongest supportable statement is:
on the preserved cache, simple
raw-proxy verified scheduling beats the available ARC adaptation over most of
the curve, while frozen PSTR is better overall; the complete proposed system
has not been shown superior to ARC under a common physical deadline.
