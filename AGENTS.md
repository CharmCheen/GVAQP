# AGENTS.md

## Project Scope

This repository studies G-ARC: Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories.

The current stage is benchmark construction and SUPG/ARC-related reproduction. Do not treat this repo as being ready for full G-ARC method invention unless the user explicitly redirects the work.

## Environment

- Repository path: `/qiuyeqing/llama_prl/G-ARC`
- Typical setup: `cd /qiuyeqing/llama_prl/G-ARC && source env_garc.sh`
- Conda environment: `garc`
- YOLO model paths:
  - `models/yolo/yolov8n.pt`
  - `models/yolo/yolov8x.pt`
- Default proxy model: YOLOv8n
- Default pseudo-oracle model: YOLOv8x

## Repository Layout

- `garc_eval/`: main benchmark, reproduction, metric, adapter, dataset, config, and experiment code.
- `garc_eval/outputs/`: lightweight reports and experiment summaries.
- `garc_eval/configs/`: lightweight experiment configuration files.
- `data/`: local datasets and derived frame/table assets; treat as large local state.
- `models/`: local model weights; treat as large local state.
- `refe_repos/`: reference repositories; read-only for normal work.

## Do-Not-Modify Rules

- Do not modify `refe_repos/`.
- Do not commit or stage large files.
- Do not commit or stage `data/`, `models/`, `*.pt`, `*.zip`, `*.png`, `*.parquet`, or `*.csv`.
- Lightweight markdown reports under `garc_eval/outputs/` may be created or modified.
- Lightweight config files may be created or modified.

## Current Validated Findings

- SUPG synthetic reproduction is complete at the algorithm level (algorithm-level reproduction, not full paper reproduction).
- KITTI 0005 and combined KITTI are degenerate for SUPG-RT: too small, too positive, SUPG-RT selects all. Do not present as successful non-degenerate benchmarks.
- KITTI should only be kept as a pipeline smoke benchmark.
- DRIV100 was blocked because the accessible record lacks raw videos.
- BDD100K is a valid non-vacuous frame-level SUPG-RT benchmark (image-level only, no temporal continuity).
- UA-DETRAC is a valid temporal smoke/pipeline benchmark; SUPG-RT often selects all on current settings.
- SUPG-PT works under tested settings but is a high-precision/low-recall operating point.
- Do not claim G-ARC theory is complete or formal guarantees beyond what has been implemented and tested.
- Do not spend more time tuning KITTI unless explicitly asked.

## Current Target

Find a larger real traffic/video dataset suitable for non-degenerate SUPG and later clip-level G-ARC experiments.

Preferred dataset properties:

- `N >= 10,000` frames.
- Positive rate between 1% and 20% after calibrating `count_car(frame) >= K`.
- High proxy score uniqueness.
- `SUPG-RT selected_n / N < 0.95` in smoke trials.
- Meaningful SUPG-PT precision/recall tradeoff.
- Temporal continuity so selected frames can be merged into candidate clips.

## Query Setting

- Predicate: `count_car(frame) >= K`.
- Default proxy score rule: `count_conf_hybrid` if available.
- Do not claim the YOLOv8x pseudo-oracle is human ground truth.

## Experiment Policy

Use staged evaluation:

1. Dataset acquisition audit.
2. Controlled subset download.
3. Frame extraction or image sequence loading.
4. Proxy/oracle materialization.
5. `K` calibration.
6. 5-trial smoke.
7. Only if non-degenerate, suggest a 20-trial next step.
8. Do not run 100-trial formal experiments unless explicitly authorized.

Do not run experiments or download datasets unless the user explicitly asks.

## AQP / VLM Budget Experiment Constraints

- Any new experiment must write to a new independent output directory. Do not overwrite existing CSV files, videos, VLM labels, or formal results.
- Conservative VLM full-scan labels are evaluation-only pseudo-oracle labels. Do not use them for ranking, candidate cluster construction, hyperparameter selection, feature training, or learned proxy training.
- Learned proxy train/validation/test splits must be grouped by source video or original video group. Do not randomly split adjacent clips from the same source video across splits.
- Current-stage results must be described as pseudo-oracle or VLM-defined evaluation. Do not describe them as real risk-event ground truth.
- Before implementing a new method, search for and reuse existing scripts, CSV schemas, budget simulation code, and temporal NMS implementations.
- Every experiment must run a smoke test before a full run and must record commands, random seeds, input files, runtime, and failure reasons.
- Random baselines must run at least 100 repeats and report mean, standard deviation, and 95% intervals.
- Every newly added algorithm must include sanity checks. If sanity checks fail, fix the implementation before interpreting results.
- The current stage does not require human audit, audit package generation, or new large-scale VLM inference.
- Final experiment outputs must include a Markdown report, CSV tables, figures, reproducible commands, and a clear `GO`, `WEAK GO`, or `NO-GO` decision.

## Reporting Requirements

- Always write lightweight markdown reports under `garc_eval/outputs/`.
- Reports must distinguish engineering smoke results from research-valid conclusions.
- Reports must explicitly document failed hypotheses, limitations, and uncertainty.
