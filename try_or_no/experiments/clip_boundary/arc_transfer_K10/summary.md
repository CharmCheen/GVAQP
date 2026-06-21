# ARC Transfer Stress Test Summary

- CSV: `/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv`
- Label: `label_K10`
- Frames: 5000
- True clips: 18
- Positive ratio: 0.3736

## Group 1: Proxy Candidate Upper Bound

Top 10 by refined_unlimited_recall:

| proxy | thr | gap | proxy_recall | refined_recall | cand_frac | oracle_needed |
|-------|-----|-----|-------------|---------------|-----------|--------------|
| proxy_positive_K5 | binary | 5 | 0.056 | 1.000 | 0.604 | 3228 |
| proxy_vehicle_count | top50% | 10 | 0.056 | 1.000 | 0.545 | 3021 |
| proxy_positive_K5 | binary | 10 | 0.056 | 1.000 | 0.604 | 3366 |
| proxy_vehicle_count | top50% | 15 | 0.000 | 1.000 | 0.545 | 3150 |
| proxy_vehicle_count | top50% | 30 | 0.000 | 1.000 | 0.545 | 3225 |
| proxy_positive_K5 | binary | 30 | 0.000 | 1.000 | 0.604 | 3418 |
| proxy_positive_K5 | binary | 15 | 0.000 | 1.000 | 0.604 | 3400 |
| proxy_score | top50% | 30 | 0.056 | 0.944 | 0.500 | 2988 |
| proxy_vehicle_count | top40% | 30 | 0.056 | 0.944 | 0.406 | 2743 |
| proxy_vehicle_count | top50% | 5 | 0.056 | 0.944 | 0.545 | 2942 |

## Group 2: Budgeted ARC-like Refinement

- Budget 50: best recall=0.056 (proxy_score, proxy_mean_desc, invalid=0.0%)
- Budget 100: best recall=0.111 (proxy_vehicle_count, proxy_score_desc, invalid=0.0%)
- Budget 200: best recall=0.222 (proxy_vehicle_count, proxy_score_desc, invalid=0.0%)
- Budget 400: best recall=0.278 (proxy_vehicle_count, proxy_score_desc, invalid=0.0%)
- Budget 800: best recall=0.500 (proxy_vehicle_count, uncertainty_first, invalid=0.0%)
- Budget 1200: best recall=0.611 (proxy_vehicle_count, proxy_mean_desc, invalid=0.0%)

## Group 3: Temporal Clustering Ablation

- proxy_score top20%: no-cluster=0.444, best-cluster=0.444 (eps=0.001), delta=+0.000
- proxy_score top30%: no-cluster=0.722, best-cluster=0.722 (eps=0.001), delta=+0.000
- proxy_vehicle_count top20%: no-cluster=0.444, best-cluster=0.444 (eps=0.001), delta=+0.000
- proxy_vehicle_count top30%: no-cluster=0.722, best-cluster=0.722 (eps=0.001), delta=+0.000
- proxy_positive_K10 binary: no-cluster=0.611, best-cluster=0.611 (eps=0.001), delta=+0.000

## Group 4: Non-candidate Miss Analysis

- proxy_score top20% gap=3: covered=15/18, missed=3, nc_pos_rate=0.264, audit@200=3
- proxy_score top30% gap=5: covered=16/18, missed=2, nc_pos_rate=0.206, audit@200=1
- proxy_vehicle_count top20% gap=3: covered=15/18, missed=3, nc_pos_rate=0.250, audit@200=3
- proxy_vehicle_count top30% gap=5: covered=17/18, missed=1, nc_pos_rate=0.196, audit@200=1
- proxy_positive_K10 binary gap=5: covered=15/18, missed=3, nc_pos_rate=0.250, audit@200=2

## Judgments

1. **refined_unlimited_recall HIGH** (1.000): ARC candidate generation is effective. Main problem is budgeted refinement. Research → better oracle allocation.
2. **Temporal clustering NEUTRAL** (avg +0.000): No effect on moving-camera video. ARC temporal locality assumption does not transfer.
3. **Non-candidate audit FINDS missed clips** (up to 3/3): Recall audit has research space under weak proxy.
