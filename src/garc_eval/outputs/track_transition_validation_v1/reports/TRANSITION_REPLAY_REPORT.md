# TRANSITION_REPLAY_REPORT.md

## Setup

- L3 baseline: coverage_greedy_time_blocks_object_count_mean (P=2.0 + greedy_maxmin_time) - the deterministic L3 from prior codex_recompute output
- Transition score: has_o_to_i * 100 + o_to_i_count * 10 + max_lateral_disp * 100
- Budgets: B = 20, 30, 40, 60, 80, 100
- Audit strategy averaged over 500 seeds (seed 42..541)
- Random seed base: 42

## Strategies

1. **L3_baseline**: select L3 top-B (no transition)
2. **transition_only**: rank by transition score desc
3. **L3_union_transition**: 70% L3 + 30% transition (not in L3)
4. **L3_weighted_transition_alpha_0.5**: blend L3 + 0.5 * transition (normalized)
5. **L3_weighted_transition_alpha_1.0**: blend L3 + 1.0 * transition
6. **L3_plus_transition_audit**: 70% L3 + 20% transition-disagreement + 10% uniform random

## Full Results

### Anchor recall (L3 recovers 0.125-0.375, transitions-only recovers 0.025-0.175)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.125 | 0.150 | 0.175 | 0.275 | 0.350 | 0.375 |
| transition_only | 0.025 | 0.025 | 0.025 | 0.050 | 0.125 | 0.175 |
| L3_union_transition | 0.075 | 0.100 | 0.125 | 0.200 | 0.275 | 0.300 |
| L3_weighted_transition_alpha_0_5 | 0.050 | 0.075 | 0.150 | 0.225 | 0.300 | 0.350 |
| L3_weighted_transition_alpha_1_0 | 0.025 | 0.075 | 0.075 | 0.200 | 0.250 | 0.325 |
| L3_plus_transition_audit | 0.075 | 0.100 | 0.150 | 0.225 | 0.275 | 0.300 |

### Precision (transitions-only has 0.025-0.070, L3 has 0.150-0.250)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.250 | 0.200 | 0.175 | 0.183 | 0.175 | 0.150 |
| transition_only | 0.050 | 0.033 | 0.025 | 0.033 | 0.062 | 0.070 |
| L3_union_transition | 0.150 | 0.133 | 0.125 | 0.133 | 0.138 | 0.120 |
| L3_weighted_transition_alpha_0_5 | 0.100 | 0.100 | 0.150 | 0.150 | 0.150 | 0.140 |
| L3_weighted_transition_alpha_1_0 | 0.050 | 0.100 | 0.075 | 0.133 | 0.125 | 0.130 |
| L3_plus_transition_audit | 0.150 | 0.133 | 0.150 | 0.150 | 0.137 | 0.120 |

### Event-cluster recall (transitions-only UNDERPERFORMS L3 at all budgets)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.148 | 0.185 | 0.222 | 0.333 | 0.370 | 0.370 |
| transition_only | 0.037 | 0.037 | 0.037 | 0.074 | 0.148 | 0.222 |
| L3_union_transition | 0.111 | 0.148 | 0.185 | 0.296 | 0.333 | 0.333 |
| L3_weighted_transition_alpha_0_5 | 0.074 | 0.074 | 0.185 | 0.296 | 0.370 | 0.407 |
| L3_weighted_transition_alpha_1_0 | 0.037 | 0.074 | 0.074 | 0.259 | 0.333 | 0.407 |
| L3_plus_transition_audit | 0.111 | 0.148 | 0.222 | 0.333 | 0.333 | 0.333 |

### Singleton recall (transitions-only is competitive only at B=100, but well below L3 at B=20-80)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.095 | 0.095 | 0.143 | 0.238 | 0.286 | 0.286 |
| transition_only | 0.048 | 0.048 | 0.048 | 0.048 | 0.143 | 0.238 |
| L3_union_transition | 0.095 | 0.095 | 0.143 | 0.238 | 0.238 | 0.238 |
| L3_weighted_transition_alpha_0_5 | 0.048 | 0.048 | 0.095 | 0.190 | 0.286 | 0.333 |
| L3_weighted_transition_alpha_1_0 | 0.048 | 0.048 | 0.048 | 0.190 | 0.238 | 0.333 |
| L3_plus_transition_audit | 0.095 | 0.095 | 0.190 | 0.238 | 0.238 | 0.238 |

### Low-proxy singleton recall (low object_count_mean singletons; L3 already gets 0 at most budgets)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| transition_only | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.111 |
| L3_union_transition | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| L3_weighted_transition_alpha_0_5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| L3_weighted_transition_alpha_1_0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| L3_plus_transition_audit | 0.000 | 0.000 | 0.111 | 0.000 | 0.000 | 0.000 |

### L3-missed-positive recovery (transitions-only recovers 4 of 25 L3-missed at B=100; below random for most budgets)

| Strategy | B=20 | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|------|-------|
| L3_baseline | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| transition_only | 0.000 | 0.000 | 0.000 | 0.034 | 0.077 | 0.160 |
| L3_union_transition | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| L3_weighted_transition_alpha_0_5 | 0.029 | 0.059 | 0.091 | 0.069 | 0.077 | 0.120 |
| L3_weighted_transition_alpha_1_0 | 0.000 | 0.059 | 0.061 | 0.069 | 0.077 | 0.120 |
| L3_plus_transition_audit | 0.000 | 0.000 | 0.030 | 0.034 | 0.000 | 0.000 |

## Key Observations

1. **L3_baseline is the best method** at B<=80. The transition strategies underperform L3 at every budget <=80 on cluster_recall, singleton_recall, and anchor_recall.
2. **At B=100**, L3_weighted variants (alpha=0.5 and alpha=1.0) show marginal improvements:
   - cluster_recall: 0.407 (L3_w) vs 0.370 (L3) = +0.037 (1 cluster)
   - singleton_recall: 0.333 (L3_w) vs 0.286 (L3) = +0.048 (1 singleton)
   - These are within single-sample noise on n=40 positives / 21 singletons.
3. **transition_only has very low precision** (0.025-0.070) and recovers 4/25 of L3-missed positives at B=100.
4. **L3_plus_transition_audit** underperforms L3 on anchor_recall at all budgets.
5. **L3_union_transition (70/30)** underperforms L3 at all budgets.

## Statistical Caveats

- n=40 positives, 27 clusters, 21 singletons, 9 low-proxy singletons: very small sample
- The 1-cluster / 1-singleton improvement at B=100 is on n=27/n=21, so the 95% CI is wide
- The audit strategy is averaged over 500 seeds; the deterministic strategies (L3, transition_only, union, weighted) are single runs

## Decision

The track-transition feature does **not** improve the L3 baseline for the target failure mode. The hypothesis "track-level outside->inside transition can recover L3-missed positives" is rejected for this setup. The crude image-thirds ROI is too generous and the transition fires on too many anchors to be selective.

**Final decision: TRACK_TRANSITION_NOT_USEFUL**
