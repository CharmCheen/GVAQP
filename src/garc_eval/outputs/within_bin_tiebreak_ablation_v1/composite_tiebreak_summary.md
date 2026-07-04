# Composite Tie-Break Results

**Diagnostic only.**

## k=20 precision/recall vs random baseline (1000 reps)

| rule | precision@20 | recall@20 | events | rand mean | rand p95 | beats p95 |
| --- | --- | --- | --- | --- | --- | --- |
| inverse_boundary_quality_minus_duration | 0.3500 | 0.5000 | 3 | 0.1804 | 0.3000 | True |
| low_boundary_quality_plus_high_persistence | 0.3500 | 0.5000 | 3 | 0.1804 | 0.3000 | True |
| persistence_desc_boundary_asc | 0.3500 | 0.5000 | 3 | 0.1804 | 0.3000 | True |
| current_utility_asc | 0.3000 | 0.3333 | 2 | 0.1804 | 0.3000 | False |
| moderate_duration_plus_persistence | 0.3000 | 0.8333 | 5 | 0.1804 | 0.3000 | False |
| active_score_minus_duration_penalty | 0.2500 | 0.5000 | 3 | 0.1804 | 0.3000 | False |
| active_desc_boundary_asc | 0.2500 | 0.5000 | 3 | 0.1804 | 0.3000 | False |
| current_utility_desc | 0.2000 | 0.3333 | 2 | 0.1804 | 0.3000 | False |
| persistence_plus_boundary_drop_minus_disagreement | 0.2000 | 0.5000 | 3 | 0.1804 | 0.3000 | False |
| active_plus_persistence_minus_boundary | 0.2000 | 0.3333 | 2 | 0.1804 | 0.3000 | False |
| active_plus_boundary_drop_minus_duration | 0.2000 | 0.3333 | 2 | 0.1804 | 0.3000 | False |
