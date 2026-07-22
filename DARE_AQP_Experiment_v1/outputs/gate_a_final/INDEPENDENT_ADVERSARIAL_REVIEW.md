# Independent adversarial review — Gate A

**Verdict: `PASS`.**

| Check | Result | Evidence |
|---|---:|---|
| exact_model_repositories | PASS | ['microsoft/xclip-base-patch32', 'openai/clip-vit-base-patch32'] |
| exact_model_revisions | PASS | requested=resolved=configured |
| all_model_file_sizes_and_hashes | PASS | files=16 |
| four_signals_347_exact_units | PASS | {'current_proxy': 347, 'image_text': 347, 'rank_fusion': 347, 'video_text': 347} |
| frozen_score_metadata | PASS | all signal metadata equals frozen config |
| raw_score_seal | PASS | 5bd2201de270327ae6e6a8810a04c99009c278a2b764bf3ea561ad591c5157c4 |
| ranking_hash_and_recomputation | PASS | rankings=4 |
| static_inference_leakage_boundary | PASS | no evaluator/oracle path token in runner |
| input_and_sampling_identity | PASS | {'image_text': 'one center frame per 10-second unit', 'video_text': 'eight uniformly spaced frames per 10-second unit'} |
| complete_runtime_accounting | PASS | columns=36, rows=2 |
| frozen_gate_b_integration | PASS | rows=20 |
| decision_matches_registered_threshold | PASS | any_public_GO=False |
| physical_exact_oracle_calls_zero | PASS | 0 |
| required_evaluation_artifacts | PASS | ['ranking_metrics.csv', 'gate_b_link.csv', 'per_budget_event_metrics.csv', 'event_f1_auc.csv', 'unique_event_first_discovery.csv', 'arc_map_overlap_divergence.csv', 'ranking_diagnostics.csv', 'public_to_oracle_gap.csv', 'query_cost_normalized_results.csv', 'per_unit_runtime.csv'] |
