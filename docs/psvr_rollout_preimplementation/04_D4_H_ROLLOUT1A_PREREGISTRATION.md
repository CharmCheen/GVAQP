
# D4 — H-ROLLOUT1A preregistration

Status: `LOGICAL_PREREGISTRATION_COMPLETE`, execution status: `BLOCKED_DEPENDENCY_D2_NUMERIC_BINDING`.

The hypothesis, Ideal Symmetric Rollout Mechanism, asks whether exact full-horizon symmetric continuation evaluation improves over frozen shielded pi0, Ratio-PSVR, and the best fixed policy in continuous non-extreme regimes under exact dynamics, zero estimator noise, and zero ideal planning cost. It does not test M0 transport, a real world model, MC error, physical planning overhead/throughput, deployment, temporal refinement, or multi-fidelity.

For each safe candidate action, execute it once and then use the same pi0 to horizon. The pi0 action is always included. Exact expectation/enumeration is preferred. If MC is unavoidable, its independent stream keys, 99% absolute half-width threshold, 100-million-sample cap, and numerical-block branch are fixed in JSON and never scaled to the observed effect. Baseline action rules—including fixed periods 1/2/4/8 and the visible-posterior expected-increment/cost Ratio-PSVR—are frozen there.

The primary metric is exact-ID time-weighted unique-event utility at lambda=1; perfect Oracle makes FP zero but does not alter the registry. JSON fixes F1 empty-set behavior, normalized AUC, TTFC censoring plus indicator, exact matching, episode pairing, unweighted macro/median, nine regime cells, worst cell, heatmap bins, minimum cell size, numerical tolerance, and the three-consecutive-bin neighborhood rule. Statistical inference uses paired independent episodes, never actions, deadlines, or MC samples.

Gate A separately requires macro wins over pi0, Ratio-PSVR, and the maximum of every frozen simple arm, plus continuous positive neighborhoods in two of sparse, bursty, and heterogeneous-cost families. Gate B retains dense homogeneous evidence even if pi0 wins. Gate C uses the result-blind parameter-file rule for floor/transition/saturation, including explicit no-saturation/no-transition statuses. Gate D reports decisions, simulated trajectories, asymptotic cost, and `COMPLEXITY_NOT_YET_JUSTIFIED` when appropriate.

ACCEPT additionally requires earlier durable commits, no leakage, all named adverse scenarios, trace recomputation, and no blocking independent-review defect. A one-event jump or floating error is not scientifically meaningful without a same-direction parameter neighborhood. Partial/reject/blocked branches and all forbidden post-hoc edits are exact in the JSON.

The JSON binds exact D1/D2/D3 hashes. It must be reissued—not silently edited—after a legitimate D2 SCAN calibration. No H-ROLLOUT1A execution is authorized by this blocked preregistration.
