# SUPG Reproduction — Algorithm-Level Experiment

## 1. Environment Setup

```bash
# Create conda environment
conda create -n supg python=3.10 -y
conda activate supg

# Install dependencies (pip preferred due to conda network issues)
python -m pip install numpy pandas scipy matplotlib pyarrow scikit-learn tqdm pytest feather-format

# Install SUPG repo in editable mode
python -m pip install -e refe_repos/supg
```

If `import supg` fails after editable install, the adapter in `garc_eval/adapters/supg_adapter.py`
automatically falls back to `sys.path` insertion pointing at `refe_repos/supg`.

## 2. Running the Synthetic Experiment

### Smoke test (quick validation)

```bash
conda activate supg
python -m garc_eval.datasets.make_beta --n 100000 --alpha 0.01 --beta 1.0 --output garc_eval/outputs/beta_001_1.csv
python -m garc_eval.experiments.run_supg_synthetic --n 100000 --budget 1000 --gamma 0.9 --trials 5 --outdir garc_eval/outputs/supg_smoke
```

### Full experiment (100 seeds, 1M rows)

```bash
conda activate supg
python -m garc_eval.experiments.run_supg_synthetic --n 1000000 --budget 10000 --gamma 0.9 --trials 100 --outdir garc_eval/outputs/supg_full
```

### Command-line arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--n` | 1000000 | Number of data points |
| `--alpha` | 0.01 | Beta distribution alpha parameter |
| `--beta` | 1.0 | Beta distribution beta parameter |
| `--budget` | 10000 | Oracle query budget |
| `--gamma` | 0.9 | Target recall (RT) or precision (PT) |
| `--delta` | 0.05 | Significance level for confidence intervals |
| `--trials` | 100 | Number of random seeds |
| `--outdir` | garc_eval/outputs | Output directory |

## 3. Proxy and Oracle in This Reproduction

- **proxy_score = A(x)**: The proxy/confidence score, generated from Beta(alpha, beta).
  In the real SUPG system, this would be the output of a cheap neural network (e.g., YOLO).
  In this synthetic setting, it is drawn directly from a Beta distribution.

- **label = O(x)**: The oracle/ground-truth label, generated as Bernoulli(proxy_score).
  In the real system, this would be the output of an expensive model (e.g., Mask R-CNN)
  or a human annotator. Here it is a coin flip weighted by the proxy score.

## 4. Synthetic Beta Data Model

Following the SUPG paper's simulation:

- A(x) ~ Beta(alpha, beta) — a continuous score in [0, 1]
- O(x) ~ Bernoulli(A(x)) — binary label, positively correlated with the proxy

The default configurations are:
- Beta(0.01, 1): high average proxy score, high base rate
- Beta(0.01, 2): lower average proxy score, more skewed

With alpha=0.01, the Beta distribution is heavily right-skewed, meaning most items have
low proxy scores and few have high scores — mimicking the sparsity pattern of real
object detection (most frames contain no target object).

## 5. Baselines

### U-NOCI (Uniform + No Confidence Interval)

Uniform random sampling + empirical threshold selection without any statistical guarantee.

- **U-NOCI-RT**: Sample uniformly, find the largest threshold where sample recall >= gamma,
  return all items above that threshold union sample positives.
- **U-NOCI-PT**: Sample uniformly, find the threshold where sample precision >= gamma that
  returns the most items, return those union sample positives.

This baseline has NO guarantee — it may fail the target on the full dataset.

### U-CI (Uniform + Confidence Interval)

Uniform random sampling + normal-approximation confidence interval for conservative threshold selection.

- **U-CI-RT**: Uses a z-score based CI on the recall estimate at each candidate threshold.
  Selects the largest threshold where the CI lower bound >= gamma.

> **Note**: U-CI-RT is implemented as a best-effort baseline using normal approximation.
> Check against SUPG Algorithm 2 before publication use.

### SUPG (Importance Sampling + Confidence Interval)

The full SUPG method from the paper:

- **SUPG-RT**: Uses sqrt-weighted importance sampling (the theoretically correct weighting)
  with Hoeffding-based confidence intervals for conservative recall threshold selection.
- **SUPG-PT**: Uses two-stage importance sampling with sqrt weighting and confidence
  intervals for conservative precision threshold selection.

## 6. Output Files

| File | Description |
|------|-------------|
| `config.json` | Experiment parameters |
| `synthetic_beta.csv` | Generated dataset |
| `per_trial_results.csv` | Per-seed results for all methods |
| `summary.csv` | Aggregated statistics per method |
| `boxplot_rt_recall.png` | Recall distribution boxplot (RT methods) |
| `boxplot_pt_precision.png` | Precision distribution boxplot (PT methods) |

## 7. Scope and Limitations

This is an **algorithm-level reproduction** of the SUPG paper. The smoke test
validates the code pipeline and qualitative trends only; it does not constitute
a formal reproduction of the paper's results.

- We reproduce the sampling, threshold selection, and confidence interval logic.
- We use synthetic Beta data to simulate the proxy-oracle relationship.
- We do NOT involve YOLO, Mask R-CNN, or real video frames.

### Future Extension to Real Video

To run on real video frames, convert frame-level detections to the format:

```
id,label,proxy_score
0,1,0.95
1,0,0.12
...
```

where `proxy_score` is the cheap detector's confidence and `label` is the expensive
detector's ground truth. The rest of the pipeline remains identical.

## 8. Real Frame-Level Proxy/Oracle Pipeline

The SUPG algorithm operates on a table with columns `id, label, proxy_score`.
The real pipeline generates this table by running models on video frames offline.
Once the table exists, SUPG runs exactly the same way as in the synthetic experiments —
100 trials only read cached scores, not re-run models.

> **Current status**: The code framework is complete and passes local dry-run and
> fake-real integration tests. No real model inference has been run yet.
> Real inference requires a server with GPU and the actual YOLO models.
> See `garc_eval/scripts/server_setup_env.md` for server setup instructions.

### Recommended Models

| Role | Model | Rationale |
|------|-------|-----------|
| Proxy (cheap) | YOLOv8n | Fast (~6MB), suitable for screening |
| Oracle (expensive) | YOLOv8x | Larger, more accurate detections |
| Oracle (alt) | Ground-truth labels | If available, avoids running oracle model |

Mask R-CNN can be added as a future oracle extension. Current stage is frame-level only, not clip-level.

### Pipeline Steps

1. **Extract frames** — `garc_eval/datasets/extract_video_frames.py`
2. **Materialize scores** — `garc_eval/experiments/materialize_frame_scores.py`
   - Runs proxy model on all frames → `proxy_scores.parquet`
   - Runs oracle model (or reads GT) → `oracle_scores.parquet`
   - Builds `frames.parquet` and `supg_source.csv`
3. **Run SUPG** — `garc_eval/experiments/run_supg_real_frames.py`
   - Reads `supg_source.csv` (id, label, proxy_score)
   - Runs U-NOCI, U-CI, SUPG across N trials

### Configuration

See `garc_eval/configs/real_frame_yolo.example.yaml` for all settings.
Paths use `${GARC_MODEL_DIR}` etc. — resolved from environment variables.

### Server Setup

See `garc_eval/scripts/server_setup_env.md` for environment setup,
model placement, and dependency installation.

## 9. Third-Party Repo Commit Hashes

Recorded in `garc_eval/outputs/repo_commits.json`.
