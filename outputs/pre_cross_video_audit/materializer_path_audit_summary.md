# Stage 0.7b Materializer Trigger / Path Audit

- audited rows: 810
- optional trigger summary: `{'blocked_by_proxy_valley': 708, 'selected_expansion_attempt_count': 6008, 'selected_expansion_applied_count': 2546, 'duplicate_candidate_pairs': 0, 'duplicate_suppressed_count': 0, 'output_changed_vs_K3': 310}`
- K3/K4/C6 aggregate metric equality: True
- compression summary: `[{'materializer_variant': 'C6_full_EVENT_MATERIALIZE', 'event_F1_AUC': 0.4069927107830243, 'B20_F1': 0.2458220469814672, 'B100_F1': 0.5691076654318525}, {'materializer_variant': 'K0_naive_merge', 'event_F1_AUC': 0.0772486772486772, 'B20_F1': 0.0783068783068783, 'B100_F1': 0.0783068783068783}, {'materializer_variant': 'K1_gap_limited', 'event_F1_AUC': 0.3667153422308711, 'B20_F1': 0.2465152668051219, 'B100_F1': 0.4795419382157733}, {'materializer_variant': 'K2_gap_duration', 'event_F1_AUC': 0.3893499174494699, 'B20_F1': 0.2458220469814672, 'B100_F1': 0.5288703691150854}, {'materializer_variant': 'K3_gap_duration_negative_barrier', 'event_F1_AUC': 0.4069927107830243, 'B20_F1': 0.2458220469814672, 'B100_F1': 0.5691076654318525}, {'materializer_variant': 'K4_gap_duration_negative_barrier_selected_expand', 'event_F1_AUC': 0.4069927107830243, 'B20_F1': 0.2458220469814672, 'B100_F1': 0.5691076654318525}]`
- classification: Case B_metric_nonimpactful

K3/C6 equality in Stage 0.7 is metric equality, not byte-for-byte segment equality. Optional C6/K4 mechanisms are exercised and sometimes change segment files, but the frozen K3 decision is legitimate when AUC/B20/B100 remain equal and no path alias or evaluator bug is observed.
