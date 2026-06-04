# Reference Repo Notes

## SUPG: Minimal Input Table

**Required CSV columns:**
- `id` — 0-indexed, sequential integer
- `label` — True/False (or 1/0), the oracle ground-truth label
- `proxy_score` — float between 0 and 1, the cheap proxy score

**Main API:**
```python
from supg import run_rt, run_pt
run_rt(csv_fname, budget, rt)  # Recall target
run_pt(csv_fname, budget, rt)  # Precision target
```

**How it works:**
1. `DFDataSource` loads the CSV, sorts by `proxy_score` descending.
2. `ImportanceSampler` draws `budget` items with `sqrt(proxy_score)` weights (mixed with 10% uniform).
3. `RecallSelector` finds a proxy-score threshold such that the weighted positive mass below it reaches `min_recall * total_positive_mass`. Uses Hoeffding-style sampling bounds to adjust the threshold.
4. `ImportancePrecisionSelector` walks down the sorted sample, using sampling bounds to find where estimated precision exceeds `min_precision`.
5. The returned set is a contiguous prefix of the proxy-sorted list (all items with proxy >= threshold), union with sampled positives.

**Key insight:** The method returns a *set* (not a sample). The budget controls how many oracle labels are *inspected* to determine the threshold, not the size of the returned set.

**Experiment structure:**
- `experiments/experiment.py` defines experiments via `exp_dict.py`
- `TrialRunner` runs multiple trials with different seeds
- Reports: precision, recall, coverage (whether target was met), set size, oracle calls

---

## ABae: Minimal Input Table

**Required columns (CSV):**
- `proxy_scores` — float, proxy/cheap score for ordering
- `statistics` — float, the aggregation target value (e.g., vehicle count)
- `predicates` — boolean, whether the expensive predicate is true

**Key class: `Records`**
- Takes `k` (number of strata), `proxy_scores`, `statistics`, `predicates`
- Sorts by `proxy_score`, splits into `k` strata
- Computes per-stratum: `p_i` (positive rate), `sigma_i` (std of statistics among positives), `m_i` (mean of statistics among positives)
- `ground_truth = statistics[predicates].mean()` — the exact answer

**How experiments work:**
1. Two-phase sampling: Phase 1 (pilot) samples `n1` per stratum, Phase 2 allocates remaining budget proportional to `sqrt(p_i) * sigma_i`
2. `_execute_ours`: ABae's stratified method with pilot + optimized allocation
3. `_execute_uniform`: Uniform sampling baseline
4. Reports: MSE, CI width, CI coverage

**Key insight:** The optimal allocation for AVG(statistics | predicate) is proportional to `sqrt(p) * sigma`, not just `p` or `sigma` alone. This is the core ABae contribution.

---

## Reusable Ideas

1. **SUPG's interface pattern**: CSV with `id, label, proxy_score` is clean and general.
2. **Importance sampling with sqrt(proxy) weights**: Theoretically motivated, easy to implement.
3. **Sampling bounds**: Hoeffding-style bounds for confidence intervals on sampled quantities.
4. **ABae's two-phase allocation**: Pilot → estimate stratum stats → allocate remaining budget.
5. **ABae's Records class**: Clean abstraction for stratified data with precomputed stats.
6. **TrialRunner pattern**: Run N trials with different seeds, report mean ± std.

## What NOT to Copy

1. **SUPG's `drop_p` parameter**: Drops positive examples to simulate rare predicates. We have real rare predicates.
2. **ABae's `ray` dependency**: For our MVP, sequential execution is fine. Ray adds complexity.
3. **ABae's hardcoded paths**: `HOME = "/future/u/jtguibas/abae/data/"` — we use relative paths.
4. **ABae's `mystic` dependency**: For simple optimization, scipy.optimize suffices.
5. **SUPG's feather format**: We use CSV for simplicity.
