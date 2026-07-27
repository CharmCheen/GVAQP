# Failure Analysis

## Decisive evidence

- Design-selected P0 Recall@20 is 0.271/0.264, versus offline full-information 0.614/0.513. Missed observable headroom is 0.343/0.249.
- Nested complete-video LOVO does not establish stable ranking:
- Train `PSP_V1_LONG` → test `PSP_V0_SHORT` selected `histogram_l1_change__mean`: Recall@20=0.214, random=0.192, AUC=0.492.
- Train `PSP_V0_SHORT` → test `PSP_V1_LONG` selected `saturation_mean__mean`: Recall@20=0.197, random=0.195, AUC=0.492.
- Candidate Brier is 0.298/0.252; count MAE is 1.028/1.038.
- Removing the globally highest-count region leaves Recall@20 0.227/0.271; maximum selected-region contribution is 0.211.
- Proxy missingness is zero, so missing observations do not explain failure.
- Preview cost is dominated by decode, not feature computation, and makes 60-second net yield negative.

## Required error artifacts

- High-score/no-event regions: `experiments/models/high_score_zero_event_regions.csv`.
- Low-score/high-event regions: `experiments/models/low_score_positive_event_regions.csv`.
- Cross-video direction, oracle headroom, model-versus-heuristic disagreement, time-index confounding, single-region contribution, missingness, and cost decomposition: `metrics/failure_analysis_metrics.json`.

The main competing explanation is pseudo-reference or midpoint-label noise. It cannot fully explain the gap because the same labels admit a much stronger full-information order.

`P1_LOW_RATE_DETECTION_OR_P2_SPARSE_MOTION_MAY_CLOSE_OBSERVABILITY_GAP` is a **CANDIDATE_HYPOTHESIS**, not an established direction and not an allowed post-hoc extension of MRPO-V1.
