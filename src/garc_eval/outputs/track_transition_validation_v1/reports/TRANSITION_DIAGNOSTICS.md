# TRANSITION_DIAGNOSTICS.md

## Question 1: Does transition cover L3-missed positives?

**Partially yes, but not selectively enough.**

Base transition rate: 83.6% (290/347 anchors have any o->i transition)
Qwen-positive transition rate: 65.0% (26/40)
Qwen-negative transition rate: 86.0% (264/307)

The transition feature is **NOT enriched for positives** (enrichment 0.78x vs base, 0.76x vs negatives). It is actually slightly under-enriched on positives. The transition is "vehicle moves laterally through the lower-center band" which is common on busy highways (e.g., normal lane changes).

L3-missed positive recovery (per budget, transition_only strategy):

| Budget | L3 hit pos | L3-missed pos | transition-recovered | recovery rate |
|--------|-----------|---------------|---------------------|---------------|
| 20 | 5 | 35 | 21 | 60.0% |
| 30 | 6 | 34 | 20 | 58.8% |
| 40 | 7 | 33 | 19 | 57.6% |
| 60 | 11 | 29 | 15 | 51.7% |
| 80 | 14 | 26 | 14 | 53.8% |
| 100 | 15 | 25 | 13 | 52.0% |


## Question 2: Does transition cover low-proxy singleton positives?

**No, transition is UNDER-enriched on low-proxy singletons.**

Low-proxy singleton positives (object_count_mean <= 6.5, n=9): only 4/9 = 44.4% have o->i transition.

This is the **target failure mode** of the original hypothesis: low-proxy singletons should be enriched with transitions, but they are NOT.

## Question 3: Is transition complementary to L3, or highly overlapping?

**High overlap with L3, low complementarity.**

| Budget | Overlap with L3 (transition_only) | L3_missed_positive_recovery |
|--------|----------------------------------|------------------------------|
| 20 | 25.0% | 0.0% |
| 30 | 23.3% | 0.0% |
| 40 | 30.0% | 0.0% |
| 60 | 33.3% | 3.4% |
| 80 | 41.2% | 7.7% |
| 100 | 45.0% | 16.0% |


**transition_only overlap with L3 is 25-45%**, which is moderate, not extreme. But the **directional recovery is poor**: of the 35 L3-missed positives at B=20, transition_only recovers 0 — but at the cost of missing 4 of L3's 5 hits. Net negative.

## Question 4: Is transition just selecting more high-density regions?

**Yes, and that's the problem.**

With 83.6% base rate, transition fires on most anchors. It's essentially a "lateral movement detector" that captures normal highway activity. Adding it to L3 mostly adds noise (false positives on busy negative anchors), so the weighted/union/audit variants underperform L3.

## Group-level diagnostic table

| Group | n | with o->i | rate | enrichment vs base |
|-------|---|-----------|------|--------------------|
| all_anchors | 347 | 290 | 83.6% | 1.00x |
| qwen_positives | 40 | 26 | 65.0% | 0.78x |
| qwen_negatives | 307 | 264 | 86.0% | 1.03x |
| singleton_positives | 21 | 14 | 66.7% | 0.80x |
| multi_anchor_positives | 19 | 12 | 63.2% | 0.76x |
| low_proxy_positives | 14 | 5 | 35.7% | 0.43x |
| low_proxy_singleton_positives | 9 | 4 | 44.4% | 0.53x |


## Conclusion

The track-transition hypothesis is **not supported** for this setup. The transition feature:

1. Has very high base rate (83.6%) — not selective
2. Is **under-enriched on positives** (0.78x vs base) — opposite of what the hypothesis predicted
3. **Fails to cover low-proxy singletons** (4/9 covered, lower than 65% positive rate)
4. Adds noise rather than signal when combined with L3

The crude image-thirds ROI captures normal lane-change patterns that are common on busy highways, not the specific event pattern (object entering ego future path) that V13 VLM labels as positive. A geometric ego-corridor definition (lane detection, perspective transform) would be needed to test this hypothesis with higher fidelity.

**Decision: TRACK_TRANSITION_NOT_USEFUL** — see `tables/final_decision.csv`.
