# D3-norepair-core-chunk120 vs B6-core Identity Check

## Implementation differences

Both methods use a chunk-bandit with Thompson sampling (Gamma(N1_c + 0.1, 1/(n_c+1))) and chunk_size = 120 s, but they differ in how `N1_c` (singleton-positive mass) is counted:

- **B6-core**: uses `get_event_at_bin(grid, b)` to map each sampled bin to its `event_id`, then counts per-chunk events that appear exactly once. This is `posthoc_eval` because it uses `event_id`.
- **D3-norepair-core-chunk120**: counts a sampled bin as a singleton positive if it is positive and has been sampled exactly once (no `event_id`). This is `strict_replay`.

Other details (bin size=10 s, uniform random sampling within chosen chunk, Core/Halo release, MAX_GUARDS_PER_SIDE=3) are identical because D3-norepair reuses the same `run_discovery_then_core_halo` guard/release path.

## Per-metric numerical comparison (per trial: segment × budget × seed)

| metric | mean D3nr | mean B6 | mean diff | max abs diff | frac identical |
|---|---|---|---|---|---|
| 事件精度 | 0.7571 | 0.8024 | -0.0452 | 1.0000 | 0.831 |
| 事件召回 | 0.3860 | 0.3604 | +0.0256 | 0.4444 | 0.383 |
| 时长精度 | 0.3452 | 0.3780 | -0.0328 | 1.0000 | 0.271 |
| 时长召回 | 0.3860 | 0.3604 | +0.0256 | 0.4444 | 0.383 |
| 候选区间总时长 | 93.3333 | 84.4524 | +8.8810 | 190.0000 | 0.329 |
| guard calls | 3.8548 | 6.7500 | -2.8952 | 34.0000 | 0.340 |
| discovery calls | 39.3381 | 34.0690 | +5.2690 | 54.0000 | 0.160 |
| 总 oracle calls | 43.1929 | 40.8190 | +2.3738 | 38.0000 | 0.217 |
| 命中唯一事件数 | 4.7143 | 4.3476 | +0.3667 | 6.0000 | 0.383 |
| discovery miss 数 | 8.1214 | 8.4262 | -0.3048 | 8.0000 | 0.395 |

## Segment-level mean event_recall (core release)

| segment | D3nr mean R | B6 mean R | diff |
|---|---|---|---|
| dataset3_0_1200 | 0.450 | 0.436 | +0.014 |
| dataset3_1200_2400 | 0.357 | 0.336 | +0.021 |
| dataset3_2400_3462 | 0.397 | 0.361 | +0.036 |
| realcartest_0_1570 | 0.359 | 0.312 | +0.046 |
| realcartest_2000_3200 | 0.359 | 0.338 | +0.021 |
| realcartest_3200_3830 | 0.400 | 0.389 | +0.011 |

## Identity conclusion

**Verdict: D3-norepair-core-chunk120 and B6-core are NOT numerically identical.**

The difference comes from the singleton-counting rule: B6 collapses multiple bins of the same event into one singleton count, while D3-norepair counts each positive bin separately. In this dataset this produces a measurable difference, so D3-norepair is an independently verified strong configuration.
