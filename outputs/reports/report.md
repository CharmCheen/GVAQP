# SUPG Algorithm-Level Reproduction Report

## 1. Environment

- **Conda environment name:** `supg`
- **Python path:** `D:/conda_envs/supg/python.exe`
- **Python version:** 3.10.20
- **Dependency installation:** conda-forge network was unstable (repeated `ConnectionResetError` and `IncompleteRead` failures). All scientific dependencies were ultimately installed via `python -m pip install`.
- **refe_repos/supg editable install:** Succeeded. `from supg.datasource import DataSource, DFDataSource, load_csv_source` and all selector/sampler imports verified working.
- **Windows encoding issue:** `conda run -n supg ...` triggers a `UnicodeEncodeError: 'gbk' codec` when subprocess output contains non-ASCII characters (e.g., from tqdm progress bars). This is a known Windows GBK codepage issue with `conda run`.
- **Recommended execution:** Use the environment Python directly: `"D:/conda_envs/supg/python.exe" -m <module>`.

## 2. Third-party Repository Status

Source: `garc_eval/outputs/repo_commits.json`

| Repository | Commit Hash |
|------------|-------------|
| supg | `cff4e7eb9b657e79a8f1d8e245e23bcad543126c` |
| abae | `a9a347263851b5ca510e9632f1c394257f3e343a` |
| CS2-insight-agent | `8edb9abb45abf83be876bc0e81b1078fa9ff544b` |

**No files under `refe_repos/` were modified.**

## 3. Implemented Files

All new files reside under `garc_eval/`. No third-party source code was altered.

| File | Purpose |
|------|---------|
| `garc_eval/datasets/make_beta.py` | Generates synthetic Beta datasets: proxy_score ~ Beta(alpha, beta), label ~ Bernoulli(proxy_score). CLI with `--n`, `--alpha`, `--beta`, `--seed`, `--output`. |
| `garc_eval/baselines/u_noci.py` | U-NOCI-RT and U-NOCI-PT baselines: uniform random sampling, empirical threshold selection, no confidence interval. |
| `garc_eval/baselines/u_ci.py` | U-CI-RT baseline: uniform random sampling with normal-approximation confidence interval for conservative recall threshold. Best-effort implementation. |
| `garc_eval/adapters/supg_adapter.py` | Adapter wrapping `refe_repos/supg` core classes (`RecallSelector`, `ImportancePrecisionTwoStageSelector`) into a unified `run_supg_rt` / `run_supg_pt` interface. Falls back to `sys.path` insertion if editable install has import issues. |
| `garc_eval/metrics/selection_metrics.py` | `evaluate_selection(labels, selected_ids)` returning precision, recall, selected_n, true_positive_n, total_positive_n. |
| `garc_eval/metrics/guarantee.py` | `summarize_trials(results_df, qtype, gamma)` computing failure_rate, mean/median precision/recall across trials. |
| `garc_eval/experiments/run_supg_synthetic.py` | End-to-end CLI experiment runner: generates data, runs all methods across N seeds, writes per_trial_results.csv, summary.csv, boxplots, and config.json. |
| `garc_eval/README_supg_repro.md` | Setup instructions, data model explanation, baseline descriptions, and scope notes. |
| `garc_eval/outputs/repo_commits.json` | Commit hashes of all three reference repositories. |
| `garc_eval/outputs/supg_smoke/*` | Smoke test outputs: config.json, synthetic_beta.csv, per_trial_results.csv, summary.csv, boxplot_rt_recall.png, boxplot_pt_precision.png. |

## 4. Reproduction Scope

This phase covers **algorithm-level reproduction only**. No real video frames, object detection models, or large-scale datasets are involved.

The current abstraction maps to the SUPG paper as follows:

- **proxy_score = A(x):** The cheap proxy score. In this synthetic setting, drawn from Beta(alpha, beta).
- **label = O(x):** The oracle ground-truth label. In this synthetic setting, drawn from Bernoulli(proxy_score).

This directly mirrors the SUPG paper's synthetic Beta experiment (Section 6.1 / simulation setup), where the proxy-orrelation structure is controlled by the Beta parameters.

## 5. Implemented Methods

### U-NOCI-RT / U-NOCI-PT

- Uniform random sampling of `budget` rows from the dataset.
- Empirical threshold selection on the sample: for RT, the largest threshold achieving sample recall >= gamma; for PT, the threshold achieving sample precision >= gamma with maximum coverage.
- **No confidence interval.** No statistical guarantee.
- Corresponds to a NOSCOPE-style / probabilistic-predicates baseline without guarantees.

### U-CI-RT

- Uniform random sampling.
- Normal-approximation confidence interval applied to the recall estimate at each candidate threshold.
- Selects the largest threshold where the CI lower bound >= gamma.
- **Best-effort implementation.** In the smoke test (1% TPR, budget=1000), the CI is extremely wide, causing the method to select the entire dataset. This is conservative / vacuous but satisfies the recall target.
- Check against SUPG Algorithm 2 before publication use.

### SUPG-RT / SUPG-PT

- Calls `refe_repos/supg` core classes directly via the adapter.
- **SUPG-RT:** Uses `RecallSelector` with `sample_mode="sqrt"` (the theoretically correct importance weighting) and Hoeffding-based `SamplingBounds` for confidence intervals.
- **SUPG-PT:** Uses `ImportancePrecisionTwoStageSelector` with sqrt importance weighting and two-stage sampling.
- The adapter creates fresh sampler/query/selector per trial and passes the seed for reproducibility.

## 6. Smoke Test Configuration

| Parameter | Value |
|-----------|-------|
| n | 100,000 |
| alpha | 0.01 |
| beta | 1.0 |
| budget | 1,000 |
| gamma | 0.9 |
| delta | 0.05 |
| trials | 5 |
| output directory | `garc_eval/outputs/supg_smoke` |

## 7. Smoke Test Results

| Method | Failure Rate | Mean Precision | Mean Recall | Mean Selected |
|--------|-------------:|---------------:|------------:|--------------:|
| U-NOCI-RT | 0.2 | 0.380 | 0.898 | 2,608 |
| U-CI-RT | 0.0 | 0.010 | 1.000 | 100,000 |
| SUPG-RT | 0.0 | 0.273 | 0.969 | 3,610 |
| U-NOCI-PT | 0.6 | 0.708 | 0.229 | 264 |
| SUPG-PT | 0.0 | 1.000 | 0.353 | 349 |

**Observations:**

- **U-NOCI** exhibits non-zero failure rates (0.2 for RT, 0.6 for PT), consistent with the expected behavior of a baseline that provides no statistical guarantee.
- **SUPG-RT and SUPG-PT** achieve 0% failure rate in this smoke test, with reasonable precision/recall tradeoffs. This is qualitatively consistent with the paper's claim that SUPG methods provide statistical guarantees.
- **U-CI-RT** returns the entire dataset (100,000 records), resulting in perfect recall but near-zero precision. The normal-approximation CI is excessively wide under the low-TPR + small-budget regime, producing a vacuous but technically valid result.
- This smoke test validates the code pipeline and qualitative trends. It does **not** constitute a formal reproduction of the paper's results.

## 8. Verification Commands

```bash
# Help check
"D:/conda_envs/supg/python.exe" -m garc_eval.datasets.make_beta --help

# Smoke test (5 trials, 100k records)
"D:/conda_envs/supg/python.exe" -m garc_eval.experiments.run_supg_synthetic \
  --n 100000 --budget 1000 --gamma 0.9 --trials 5 \
  --outdir garc_eval/outputs/supg_smoke
```

Note: `conda run -n supg ...` fails on Windows due to GBK encoding issues with non-ASCII subprocess output. Always use the Python absolute path directly.

## 9. Known Issues

1. **U-CI-RT is overly conservative.** In the smoke test it degenerates to selecting all records. The normal-approximation CI formula needs to be audited against SUPG Algorithm 2; the current implementation may not match the paper's intended bound.
2. **id vs. DataFrame index alignment.** The current code uses `df["id"]` values (from the CSV column) as the selection target. This needs careful auditing to ensure no confusion between `df["id"]` and `df.index`, especially when preparing for `frames.parquet` input where the id scheme may differ.
3. **SUPG seed control per trial.** The adapter creates a fresh `ImportanceSampler(seed=...)`, `ApproxQuery`, and selector for each trial call. This should ensure independent randomness per seed, but needs verification that no shared mutable state leaks across trials.
4. **Smoke test only (5 trials).** The current run uses 5 seeds as a pipeline check. Formal experiments require 100 trials per configuration for stable failure-rate estimates.
5. **No video-level components.** Frame-level video adapter, clip-level IoU, and real model inference are not implemented in this phase.

## 10. Next Steps

- [x] Audit `selected_ids` / `sampled_ids` to confirm they always correspond to `df["id"]` values and not accidental DataFrame positional indices. **PASSED**: `evaluate_selection` uses explicit `id_to_idx` mapping when `total_ids` is provided; inline test with id=[10,20,30,40] confirmed precision=1.0, recall=1.0.
- [x] Audit SUPG adapter seed control: verify each trial gets an independent random state with no cross-trial leakage. **PASSED**: Each trial call creates fresh `ImportanceSampler(seed=...)`, `ApproxQuery`, and `Selector`. No shared mutable state.
- [x] Correct README_supg_repro.md: U-CI-RT formula verification now references "check against SUPG Algorithm 2 before publication use".
- [ ] Run formal synthetic experiments:
  - Beta(0.01, 1), n=1,000,000, budget=10,000, gamma=0.9, trials=100
  - Beta(0.01, 2), n=1,000,000, budget=10,000, gamma=0.9, trials=100
- [ ] Produce formal outputs: summary.csv, summary.md, boxplots with 100-trial distributions.
- [ ] Proceed to real video `frames.parquet` experiments.
- [ ] Implement selected frames -> candidate clips -> clip-level IoU / recall / precision / mIoU / GVR pipeline.

## 11. Current Judgment

Current status: the SUPG algorithm-level reproduction framework is set up and passes a smoke test. The observed trends are consistent with the expected behavior of SUPG versus no-guarantee baselines, but formal reproduction requires code audits and 100-trial synthetic experiments before moving to video-level experiments.
