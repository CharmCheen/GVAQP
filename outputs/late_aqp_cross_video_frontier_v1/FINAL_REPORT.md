# FINAL REPORT - Cross-Video Validation of Limited-Oracle LATE-AQP Frontier

## 1. Was a qualifying second video found?

Yes. `long_video_dataset3` has a full-VLM per-anchor oracle reference (`dataset3_full_center10_parsed.csv`) and a prior score (`score_yolo_count`).

## 2. Was strict limited-oracle replay completed?

Yes. LATE-AQP-core is `strict_replay`; B6/B7/B6-core/B7-core are `posthoc_eval` because their selection logic uses per-bin `event_id`.

## 3. Did any method reach 90/90 at <=30% budget ratio on dataset3?

No. See `cross_video_precision_recall_frontier.csv` and `budget_ratio_summary.csv`.

## 4. Did LATE-AQP-core reach 90/90?

Reached on 3/3 segments:
- dataset3_0_1200: B=90, ratio=0.750, P=1.000, R=1.000
- dataset3_1200_2400: B=120, ratio=1.000, P=1.000, R=1.000
- dataset3_2400_3462: B=107, ratio=1.000, P=1.000, R=1.000

## 5. Did B7-core reach 90/90?

Reached on 3/3 segments:
- dataset3_0_1200: B=100, ratio=0.833, P=1.000, R=0.900
- dataset3_1200_2400: B=120, ratio=1.000, P=1.000, R=1.000
- dataset3_2400_3462: B=100, ratio=0.935, P=1.000, R=0.956

## 6. Is LATE-core B_90/90 <= B7-core?

- dataset3_0_1200: LATE=90, B7-core=100, LATE<=B7-core: True
- dataset3_1200_2400: LATE=120, B7-core=120, LATE<=B7-core: True
- dataset3_2400_3462: LATE=107, B7-core=100, LATE<=B7-core: False

## 7. If not always <=, is LATE-core at least closer at <=30% budget?

Best recall under P>=0.9 within the low-budget envelope:

| segment | LATE-core | B7-core | B6-core | closest |
|---------|-----------|---------|---------|---------|
| dataset3_0_1200 | 0.00 | 0.00 | 0.00 | tie (all zero) |
| dataset3_1200_2400 | 0.20 | 0.37 | 0.20 | B7-core |
| dataset3_2400_3462 | 0.33 | 0.29 | 0.27 | LATE-AQP-core |

## 8. Is Core/Halo still a generic gain?

Yes. B6-core and B7-core reach 90/90 on the same segments as LATE-AQP-core (when any method reaches), showing Core/Halo is a generic post-processing stage rather than a LATE-specific advantage.

## 9. Is the bottleneck discovery or release?

Low-budget failure taxonomy: discovery_miss=8, release_over_conservative=4, LATE-specific=3.
Most low-budget failures are discovery misses; release over-conservatism appears only for core methods after discovery has already missed events.

## 10. Recommended next step

A. Continue upstream discovery redesign; the release stage is already effective when discovery finds the events. Broader cross-video validation can wait until discovery improves.
