# Nexar-200 Return-set / Certificate Disentanglement Report

## 1. Goal

Run Phase 1.3 on the Nexar-200 derived-boundary CASQ benchmark to separate candidate-return-set quality from block/event certificate tightness. This run is metadata-only: no VLM, GPU, training, perception stack, video download, or original boundary fabrication was used.

## 2. Why previous Nexar-200 result is inconclusive

The previous reference condition had true derived recall near 0.06, median LCB recall 0, and certificate_success 0. A return set with true derived recall far below gamma=0.8 or gamma=0.9 should not certify, so that result alone cannot tell whether the certificate is too loose or the candidate set is too weak.

## 3. Return-set construction

- `R0_current_reconstructed`: reconstructed metadata-only hash top-35% 5s-unit returned clips from the prior Nexar-200 block audit script.
- `R1_oracle_exact`: one returned interval exactly equal to each derived event interval.
- `R2_oracle_padded`: derived event intervals padded by 2.5s, 5.0s, and 10.0s.
- `R3_oracle_drop`: exact derived event intervals randomly dropped to target recalls 0.5, 0.7, 0.8, and 0.9 over 10 seeds.
- `R4_event_moment_window`: 5s, 10s, and 15s windows centered at each derived event midpoint.

All oracle-informed return sets are diagnostic upper bounds or stress tests, not deployable candidate generators.

Input validation:

| check | passed | detail |
| --- | --- | --- |
| events_path_exists | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_events_nexar_200.csv |
| units_path_exists | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_200_v1/converted/casq_units_nexar_200.csv |
| usable_event_count_200 | True | rows=200 |
| all_boundaries_derived | True |  |
| event_start_lt_event_end | True |  |
| event_duration_positive | True |  |
| human_adjudicated_false | True |  |
| event_midpoint_inside_interval | True |  |
| unit_duration_positive | True |  |
| source_video_count_400 | True | videos=400 |

## 4. True derived recall by return set

| return_set_name | theta | num_returned_clips | true_derived_recall | mean_clip_duration | total_returned_duration | event_hit_count | event_total_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R0_current_reconstructed | 0.3 | 596 | 0.06 | 7.047 | 4200 | 12 | 200 |
| R1_oracle_exact | 0.3 | 200 | 1 | 1.603 | 320.6 | 200 | 200 |
| R2_oracle_padded_2p5s | 0.3 | 200 | 0.24 | 6.603 | 1321 | 48 | 200 |
| R2_oracle_padded_5p0s | 0.3 | 200 | 0 | 11.59 | 2319 | 0 | 200 |
| R2_oracle_padded_10p0s | 0.3 | 200 | 0 | 21.46 | 4292 | 0 | 200 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.3 | 160 | 0.8 | 1.648 | 263.7 | 160 | 200 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.3 | 180 | 0.9 | 1.598 | 287.7 | 180 | 200 |
| R4_event_moment_window_5p0s | 0.3 | 200 | 0.445 | 5 | 1000 | 89 | 200 |
| R4_event_moment_window_10p0s | 0.3 | 200 | 0.09 | 9.992 | 1998 | 18 | 200 |
| R4_event_moment_window_15p0s | 0.3 | 200 | 0 | 14.98 | 2996 | 0 | 200 |

Full table: `tables/return_set_true_recall.csv`.

## 5. Certificate behavior by return-set quality

The table below focuses on theta=0.3, delta=0.10, 10s blocks, and sample fractions 0.35/0.50/0.75.

| return_set_name | gamma | certification_sample_fraction | true_derived_recall | median_LCB_recall | fraction_vacuous | certificate_success_rate | GVR | tightness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0_current_reconstructed | 0.8 | 0.35 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R0_current_reconstructed | 0.8 | 0.5 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R0_current_reconstructed | 0.8 | 0.75 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R0_current_reconstructed | 0.9 | 0.35 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R0_current_reconstructed | 0.9 | 0.5 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R0_current_reconstructed | 0.9 | 0.75 | 0.06 | 0 | 1 | 0 | 0 | 0.06 |
| R1_oracle_exact | 0.8 | 0.35 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.8 | 0.5 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.8 | 0.75 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.35 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.5 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.75 | 1 | 1 | 0 | 1 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.8 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.8 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.8 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.9 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.9 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_10p0s | 0.9 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_2p5s | 0.8 | 0.35 | 0.24 | 0 | 0.785 | 0 | 0 | 0.2319 |
| R2_oracle_padded_2p5s | 0.8 | 0.5 | 0.24 | 0.04333 | 0.155 | 0 | 0 | 0.1965 |
| R2_oracle_padded_2p5s | 0.8 | 0.75 | 0.24 | 0.1321 | 0 | 0 | 0 | 0.1075 |
| R2_oracle_padded_2p5s | 0.9 | 0.35 | 0.24 | 0 | 0.755 | 0 | 0 | 0.2324 |
| R2_oracle_padded_2p5s | 0.9 | 0.5 | 0.24 | 0.04796 | 0.18 | 0 | 0 | 0.195 |
| R2_oracle_padded_2p5s | 0.9 | 0.75 | 0.24 | 0.1334 | 0 | 0 | 0 | 0.1075 |
| R2_oracle_padded_5p0s | 0.8 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_5p0s | 0.8 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_5p0s | 0.8 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_5p0s | 0.9 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_5p0s | 0.9 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R2_oracle_padded_5p0s | 0.9 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.35 | 0.8 | 0.6844 | 0 | 0.025 | 0 | 0.1176 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.5 | 0.8 | 0.7183 | 0 | 0.01 | 0 | 0.08167 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.75 | 0.8 | 0.7581 | 0 | 0.01 | 0 | 0.04129 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.35 | 0.8 | 0.694 | 0 | 0 | 0 | 0.1147 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.5 | 0.8 | 0.7183 | 0 | 0 | 0 | 0.07892 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.75 | 0.8 | 0.7555 | 0 | 0 | 0 | 0.04438 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.35 | 0.9 | 0.8283 | 0 | 0.725 | 0 | 0.07384 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.5 | 0.9 | 0.8457 | 0 | 0.955 | 0 | 0.05276 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.75 | 0.9 | 0.8694 | 0 | 1 | 0 | 0.03006 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.35 | 0.9 | 0.8276 | 0 | 0.045 | 0 | 0.07123 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.5 | 0.9 | 0.8504 | 0 | 0.025 | 0 | 0.05124 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.75 | 0.9 | 0.8694 | 0 | 0.025 | 0 | 0.02999 |
| R4_event_moment_window_10p0s | 0.8 | 0.35 | 0.09 | 0 | 1 | 0 | 0 | 0.09 |
| R4_event_moment_window_10p0s | 0.8 | 0.5 | 0.09 | 0 | 1 | 0 | 0 | 0.09 |
| R4_event_moment_window_10p0s | 0.8 | 0.75 | 0.09 | 0 | 1 | 0 | 0 | 0.09 |
| R4_event_moment_window_10p0s | 0.9 | 0.35 | 0.09 | 0 | 1 | 0 | 0 | 0.09 |
| R4_event_moment_window_10p0s | 0.9 | 0.5 | 0.09 | 0 | 1 | 0 | 0 | 0.09 |
| R4_event_moment_window_10p0s | 0.9 | 0.75 | 0.09 | 0 | 0.995 | 0 | 0 | 0.09 |
| R4_event_moment_window_15p0s | 0.8 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_15p0s | 0.8 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_15p0s | 0.8 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_15p0s | 0.9 | 0.35 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_15p0s | 0.9 | 0.5 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_15p0s | 0.9 | 0.75 | 0 | 0 | 1 | 0 | 0 | 0 |
| R4_event_moment_window_5p0s | 0.8 | 0.35 | 0.445 | 0.2238 | 0 | 0 | 0 | 0.2236 |
| R4_event_moment_window_5p0s | 0.8 | 0.5 | 0.445 | 0.2926 | 0 | 0 | 0 | 0.1581 |
| R4_event_moment_window_5p0s | 0.8 | 0.75 | 0.445 | 0.3599 | 0 | 0 | 0 | 0.08605 |
| R4_event_moment_window_5p0s | 0.9 | 0.35 | 0.445 | 0.2288 | 0 | 0 | 0 | 0.2234 |
| R4_event_moment_window_5p0s | 0.9 | 0.5 | 0.445 | 0.2872 | 0 | 0 | 0 | 0.1606 |
| R4_event_moment_window_5p0s | 0.9 | 0.75 | 0.445 | 0.3598 | 0 | 0 | 0 | 0.08609 |

Full table: `tables/disentangle_block_audit_results.csv`. Per-trial diagnostics: `tables/disentangle_block_audit_trials.csv`.

## 6. Does oracle_exact_R certify?

| return_set_name | gamma | certification_sample_fraction | true_derived_recall | median_LCB_recall | fraction_vacuous | certificate_success_rate | GVR | tightness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1_oracle_exact | 0.8 | 0.35 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.8 | 0.5 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.8 | 0.75 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.35 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.5 | 1 | 1 | 0 | 1 | 0 | 0 |
| R1_oracle_exact | 0.9 | 0.75 | 1 | 1 | 0 | 1 | 0 | 0 |

The exact oracle-informed return set has true derived recall 1.0 at both IoU thresholds. When the certification sample contains enough oracle-enumerated events for a positive denominator lower bound, its missed-event estimate is zero and the repaired bound can produce LCB recall 1.0.

## 7. Does oracle_drop_R at 0.8 / 0.9 certify?

| return_set_name | gamma | certification_sample_fraction | true_derived_recall | median_LCB_recall | fraction_vacuous | certificate_success_rate | GVR | tightness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.35 | 0.8 | 0.6844 | 0 | 0.025 | 0 | 0.1176 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.5 | 0.8 | 0.7183 | 0 | 0.01 | 0 | 0.08167 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.8 | 0.75 | 0.8 | 0.7581 | 0 | 0.01 | 0 | 0.04129 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.35 | 0.8 | 0.694 | 0 | 0 | 0 | 0.1147 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.5 | 0.8 | 0.7183 | 0 | 0 | 0 | 0.07892 |
| R3_oracle_drop_recall_0p8_seed_00 | 0.9 | 0.75 | 0.8 | 0.7555 | 0 | 0 | 0 | 0.04438 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.35 | 0.9 | 0.8283 | 0 | 0.725 | 0 | 0.07384 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.5 | 0.9 | 0.8457 | 0 | 0.955 | 0 | 0.05276 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.8 | 0.75 | 0.9 | 0.8694 | 0 | 1 | 0 | 0.03006 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.35 | 0.9 | 0.8276 | 0 | 0.045 | 0 | 0.07123 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.5 | 0.9 | 0.8504 | 0 | 0.025 | 0 | 0.05124 |
| R3_oracle_drop_recall_0p9_seed_00 | 0.9 | 0.75 | 0.9 | 0.8694 | 0 | 0.025 | 0 | 0.02999 |

The random-drop exact-interval diagnostics show whether the repaired certificate can succeed near the target operating points. Because true recall is controlled by dropping whole events, any success or failure here reflects sample-size and denominator-bound behavior rather than candidate localization error.

## 8. Is the issue candidate quality or bound tightness?

The decision rule selected `CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK`. The reconstructed current return set remains low-recall, while oracle-informed return sets test the certificate under high-quality candidate conditions. GVR is computed as the rate of successful certificates when true derived recall is below gamma; low GVR with nonzero certificate success on high-quality return sets indicates the certificate machinery can behave conservatively when candidate quality is adequate.

## 9. Limitations of derived boundaries

- Boundaries are derived from Nexar alert time to event moment; they are not original human event interval annotations.
- Results are oracle-relative to these derived intervals and must not be described as human ground truth.
- Oracle-informed return sets intentionally use derived event boundaries and are diagnostic only.
- The current return set is metadata-hash-based, not a production retrieval model or perception proxy.
- Normal-approximation finite-population bounds are inherited from the repaired Phase 0 implementation and remain a code path needing statistical review before strong claims.

## 10. Recommendation

Use Nexar-200 primarily as a certificate plumbing benchmark. The immediate bottleneck is a better non-label candidate generator that raises derived recall; the repaired certificate can certify oracle-informed high-recall return sets under reasonable sample fractions in this controlled setting.

DISENTANGLE_DECISION: CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK
