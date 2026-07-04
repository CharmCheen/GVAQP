# Answer Feature Diagnostics

Top-K precision by non-leak scores:

| score | K | answer_precision | interval_event_precision | answer_count | interval_answer_count |
| --- | --- | --- | --- | --- | --- |
| active_score | 20 | 0 | 0 | 0 | 0 |
| active_score | 50 | 0.04 | 0.04 | 2 | 2 |
| active_score | 100 | 0.09 | 0.09 | 9 | 9 |
| active_score | 200 | 0.115 | 0.115 | 23 | 23 |
| active_score | 400 | 0.1775 | 0.1775 | 71 | 71 |
| max_score | 20 | 0 | 0 | 0 | 0 |
| max_score | 50 | 0.04 | 0.04 | 2 | 2 |
| max_score | 100 | 0.09 | 0.09 | 9 | 9 |
| max_score | 200 | 0.115 | 0.115 | 23 | 23 |
| max_score | 400 | 0.1775 | 0.1775 | 71 | 71 |
| mean_score | 20 | 0 | 0 | 0 | 0 |
| mean_score | 50 | 0.02 | 0 | 1 | 0 |
| mean_score | 100 | 0.04 | 0.03 | 4 | 3 |
| mean_score | 200 | 0.045 | 0.04 | 9 | 8 |
| mean_score | 400 | 0.075 | 0.0725 | 30 | 29 |
| score_persistence | 20 | 0 | 0 | 0 | 0 |
| score_persistence | 50 | 0.02 | 0 | 1 | 0 |
| score_persistence | 100 | 0.02 | 0 | 2 | 0 |
| score_persistence | 200 | 0.03 | 0 | 6 | 0 |
| score_persistence | 400 | 0.025 | 0 | 10 | 0 |
| boundary_quality_proxy | 20 | 0.2 | 0.2 | 4 | 4 |
| boundary_quality_proxy | 50 | 0.1 | 0.1 | 5 | 5 |
| boundary_quality_proxy | 100 | 0.13 | 0.13 | 13 | 13 |
| boundary_quality_proxy | 200 | 0.11 | 0.11 | 22 | 22 |
| boundary_quality_proxy | 400 | 0.13 | 0.13 | 52 | 52 |
| answer_quality_proxy | 20 | 0.05 | 0.05 | 1 | 1 |
| answer_quality_proxy | 50 | 0.12 | 0.12 | 6 | 6 |
| answer_quality_proxy | 100 | 0.13 | 0.13 | 13 | 13 |
| answer_quality_proxy | 200 | 0.11 | 0.11 | 22 | 22 |
| answer_quality_proxy | 400 | 0.15 | 0.15 | 60 | 60 |

Method/duration concentration:

| method | duration_bin | candidates | answer_rate | interval_answer_rate | mean_active | mean_aq_proxy |
| --- | --- | --- | --- | --- | --- | --- |
| boundary_refined_expansion | 20-40 | 528 | 0.32197 | 0.32197 | 0.80752 | 0.556407 |
| threshold_merge_v2 | >80 | 90 | 0.3 | 0.3 | 0.860518 | 0.168534 |
| threshold_merge_v2 | 40-80 | 119 | 0.268908 | 0.268908 | 0.777265 | 0.330434 |
| boundary_refined_expansion | 10-20 | 75 | 0.253333 | 0.253333 | 0.680758 | 0.592611 |
| threshold_merge_v2 | 20-40 | 261 | 0.210728 | 0.210728 | 0.697806 | 0.593477 |
| signal_peak_multiscale | 20-40 | 1393 | 0.173726 | 0.173726 | 0.595018 | 0.544206 |
| fixed_window | 20-40 | 85 | 0.152941 | 0.152941 | 0.694238 | 0.542582 |
| threshold_merge_v2 | 10-20 | 374 | 0.144385 | 0.144385 | 0.649582 | 0.614478 |
| fixed_window | 10-20 | 119 | 0.134454 | 0.134454 | 0.648511 | 0.52161 |
| dense_multiscale_windows | 20-40 | 588 | 0.132653 | 0.132653 | 0.683719 | 0.588729 |
| signal_peak_multiscale | 10-20 | 1407 | 0.108031 | 0.108031 | 0.549283 | 0.51882 |
| dense_multiscale_windows | 10-20 | 1188 | 0.0799663 | 0.0799663 | 0.604431 | 0.561797 |
| threshold_merge_v2 | 5-10 | 458 | 0.0786026 | 0.0786026 | 0.586 | 0.564635 |
| signal_peak_multiscale | 5-10 | 700 | 0.0728571 | 0.0728571 | 0.518754 | 0.574583 |
| threshold_merge_v2 | 2-5 | 262 | 0.0534351 | 0.0534351 | 0.530503 | 0.497597 |
| fixed_window | 5-10 | 300 | 0.0533333 | 0.0533333 | 0.566773 | 0.483326 |
| low_density_blindspot_proposals | 20-40 | 204 | 0.0392157 | 0.0392157 | 0.620702 | 0.594064 |
| signal_peak_multiscale | 2-5 | 700 | 0.0385714 | 0.0385714 | 0.504873 | 0.44188 |
| dense_multiscale_windows | 5-10 | 1195 | 0.0384937 | 0.0384937 | 0.532095 | 0.513261 |
| low_density_blindspot_proposals | 10-20 | 214 | 0.0327103 | 0.0327103 | 0.553201 | 0.491738 |
| low_density_blindspot_proposals | 5-10 | 212 | 0.0283019 | 0.0283019 | 0.444161 | 0.6295 |
| boundary_refined_expansion | 5-10 | 47 | 0.0212766 | 0.0212766 | 0.541502 | 0.577226 |
| dense_multiscale_windows | 2-5 | 599 | 0.0200334 | 0.0200334 | 0.482571 | 0.437259 |
| boundary_refined_expansion | 2-5 | 36 | 0 | 0 | 0.3827 | 0.49961 |
| fixed_window | 2-5 | 1 | 0 | 0 | 0.437688 | 0.388784 |
| boundary_refined_expansion | <=2 | 49 | 0.0204082 | 0 | 0.174536 | 0.450319 |
| low_density_blindspot_proposals | 2-5 | 211 | 0 | 0 | 0.356697 | 0.430569 |
| threshold_merge_v2 | <=2 | 524 | 0.0267176 | 0 | 0.4957 | 0.553695 |
| boundary_refined_expansion | 40-80 | 0 | nan | nan | nan | nan |
| boundary_refined_expansion | >80 | 0 | nan | nan | nan | nan |
| dense_multiscale_windows | <=2 | 0 | nan | nan | nan | nan |
| dense_multiscale_windows | 40-80 | 0 | nan | nan | nan | nan |
| dense_multiscale_windows | >80 | 0 | nan | nan | nan | nan |
| fixed_window | <=2 | 0 | nan | nan | nan | nan |
| fixed_window | 40-80 | 0 | nan | nan | nan | nan |
| fixed_window | >80 | 0 | nan | nan | nan | nan |
| low_density_blindspot_proposals | <=2 | 0 | nan | nan | nan | nan |
| low_density_blindspot_proposals | 40-80 | 0 | nan | nan | nan | nan |
| low_density_blindspot_proposals | >80 | 0 | nan | nan | nan | nan |
| signal_peak_multiscale | <=2 | 0 | nan | nan | nan | nan |

Raw `active_score` is weakly aligned: its top prefixes contain few answer-positive candidates relative to the available 1192 positives. The hand-built `answer_quality_proxy` is diagnostic-only and uses feature-only columns.
