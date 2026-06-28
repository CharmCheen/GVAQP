# Advisor-Facing Summary

The current CASQ / G-ClipAQP work has built a single-video VLM-oracle-relative benchmark for the `O_enter_ego_path_v0` predicate and evaluated budgeted event retrieval over it. The V13.6 construction study selected 10-second centered anchors; V13.8 ran Qwen3-VL-32B over all 399 anchors; V13.9 evaluated static proxy-guided selection; and V13.10 added an OracleBest upper bound, efficiency audit, adaptive-search simulation, and metric reconciliation.

The evidence says the benchmark infrastructure is real, but the current cheap proxy methods are weak. The V13.8 reference has 94 positive anchors and 51 stitched VLM-defined events. On the full reference, V13.9/V13.10 show that YOLO/motion/geometry proxies do not recover events well at low budgets: at B=20, the best static method is uniform selection with event recall 0.137, while the OracleBest direct event-discovery upper bound is 0.392. The earlier V13.7 proxy success was on a biased labeled subset and should not be used as current method evidence.

The main uncertainty is whether a better selection signal exists. Current evidence is single-video only and VLM-oracle-relative, not human-ground-truth. Qwen3-VL-32B stability against repeated calls and human labels has not been measured. The statistical certificate layer, which is the most database/AQP-native part of the project, has not been validated on the V13.8 full oracle; earlier certificate work was underpowered.

The recommended next step is a leakage-safe predicate-conditioned scoring experiment, starting with ego-path-conditioned geometry and then a representation scorer if local assets are available. This follows directly from the failure mode: raw traffic-density proxies are misaligned with the event predicate. More simple local adaptive expansion is not recommended now because V13.10 already showed it hurts or is neutral under the current proxy scores. An 8B VLM cascade is promising but should be a controlled pilot only after explicit authorization because it requires new VLM inference.

## Safe Numbers to Cite

- V13.8 full reference: 399 center10 anchors.
- V13.8 labels: 94 positive anchors, 305 negative anchors, 0 abstain.
- V13.8 events: 51 stitched VLM-defined events.
- V13.6 center10 construction: 399 estimated full-video calls versus 798 fixed 5s calls.
- V13.10 OracleBest direct event-discovery recall: B=5 0.098, B=10 0.196, B=20 0.392, B=40 0.784, B=80 1.000.
- V13.10 best static efficiency: 0.350 at B=20 and 0.275 at B=40.

## Do Not Overclaim

- Do not cite V13.7 labeled-subset recall as current performance evidence.
- Do not call Qwen3-VL-32B labels human ground truth.
- Do not generalize V13.x results beyond `realcartest.mp4`.
- Do not use V13.9 IoU recall columns as the primary event-recall metric.
- Do not claim adaptive query execution is generally ineffective; only the tested simple adaptive mechanisms failed under current proxies.
- Do not claim the AQP certificate layer is validated on the V13.8 oracle.
