# ACTION_OPPORTUNITY_REPORT (CPU-only, model-relative)

## Oracle headroom (anytime EventF1-AUC, Q_VULNERABLE primary clusters)
- G_oracle (median over clusters) = 0.474
- G_lookahead (oracle2 - oracle1) = 0.0
- Per-cluster AUC: {
 "DALI_Q_VULN": {
  "auc": {
   "coverage_first": 0.29979,
   "oracle1": 0.77379,
   "oracle2": 0.77379,
   "relation_greedy": 0.27808,
   "top_proxy": 0.25375,
   "uniform": 0.05357
  },
  "best_fixed": "coverage_first",
  "g_lookahead": 0.0,
  "g_oracle": 0.474
 },
 "HANGZHOU_Q_VULN": {
  "auc": {
   "coverage_first": 0.31307,
   "oracle1": 0.79838,
   "oracle2": 0.79838,
   "relation_greedy": 0.33323,
   "top_proxy": 0.33323,
   "uniform": 0.19135
  },
  "best_fixed": "top_proxy",
  "g_lookahead": 0.0,
  "g_oracle": 0.46514
 },
 "WUHAN_Q_VULN": {
  "auc": {
   "coverage_first": 0.2164,
   "oracle1": 0.85307,
   "oracle2": 0.85307,
   "relation_greedy": 0.33963,
   "top_proxy": 0.33963,
   "uniform": 0.08258
  },
  "best_fixed": "top_proxy",
  "g_lookahead": 0.0,
  "g_oracle": 0.51344


## Opportunity density (terminal-delta view, epsilon thresholds)
- rho_0.01 = 0.5996260683760684   rho_0.02 = 0.5897435897435898   rho_0.05 = 0.11778846153846154
- beneficial states (gap>0.02): 2208 / 3744
- harmful action rate (<-0.02): 0.06732549857549858
- Note: state-level gap = max over sampled actions minus top-proxy action under
  top-proxy continuation; sampled-best == exhaustive-best in all sampling checks
  (ACTION_VALUE_SAMPLING_CHECK.csv), so the estimate is not an artifact of
  action subsampling.

## Context predictability (LOVO over videos, visible_* features, ridge)
- Headroom recovered = 0.3184
- model-selected gain mean = 0.00916
- oracle gain mean = 0.02876 ; baseline gain mean = 0.0
- Per-heldout rows: [
 {
  "heldout_video": "DALI",
  "mean_selected_regret": 0.01891,
  "n_test_rows": 18720,
  "n_train_states": 37440,
  "oracle_gain_mean": 0.0245,
  "pairwise_accuracy": 0.2143,
  "spearman": -0.1703
 },
 {
  "heldout_video": "HANGZHOU",
  "mean_selected_regret": 0.0103,
  "n_test_rows": 18720,
  "n_train_states": 37440,
  "oracle_gain_mean": 0.02528,
  "pairwise_accuracy": 0.2314,
  "spearman": 0.2027
 },
 {
  "heldout_video": "WUHAN",
  "mean_selected_regret": 0.0296,
  "n_test_rows": 18720,
  "n_train_states": 37440,
  "oracle_gain_mean": 0.03651,
  "pairwise_accuracy": 0.188,
  "spearman"

## Reward alignment (R0..R4 vs oracle terminal value)
                                       cluster  harmful_dev_rate_r0  harmful_dev_rate_r1  harmful_dev_rate_r2  harmful_dev_rate_r3  harmful_dev_rate_r4  spearman_r0  spearman_r1  spearman_r2  spearman_r3  spearman_r4  top_action_acc_r0  top_action_acc_r1  top_action_acc_r2  top_action_acc_r3  top_action_acc_r4
0      DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1                  1.0                  1.0                  1.0                  1.0                  1.0       0.0311      -0.0121      -0.0121      -0.0121      -0.0121             0.9712             0.8301             0.8301             0.8301             0.8301
1  HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1                  1.0                  1.0                  1.0                  1.0                  1.0       0.5275       0.1587       0.1587       0.1587       0.1587             0.8494             0.2292             0.2292             0.2292             0.2292
2     WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1                  1.0                  1.0                  1.0                  1.0                  1.0       0.5145       0.1427       0.1427       0.1427       0.1427             0.9038             0.1018             0.1018             0.1018             0.1018

## Interpretation and confounds
1. The headroom is measured against the full-grid C1 model-relative reference
   (Q_VULNERABLE). It does NOT transfer automatically to human events
   (BLOCKED_INDEPENDENT_REFERENCE) or to endogenous acquisition.
2. rho measures VERIFY-selection headroom within the fixed candidate universe:
   a different legal action at the state can beat the top-proxy action. This is
   the setting where a contextual selector could add value.
3. Proxy B per-unit scores were unavailable; features use Proxy A (reconstructed,
   validated) + temporal geometry. Cross-proxy robustness is untested here.
4. Q_DRIVER analysis (union-known labels, partial reference) is diagnostic only.
5. Costs are abstract; physical wall-clock (measured SCAN/VERIFY) is not
   part of this gate.
