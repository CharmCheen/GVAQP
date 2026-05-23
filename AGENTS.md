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

- SUPG synthetic reproduction is complete at the algorithm level.
- KITTI 0005 and combined KITTI are not valid non-degenerate SUPG-RT benchmarks because they are too small, too positive, and SUPG-RT selects all.
- KITTI should only be kept as a pipeline smoke benchmark.
- DRIV100 was blocked because the accessible record lacks raw videos.
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

## Reporting Requirements

- Always write lightweight markdown reports under `garc_eval/outputs/`.
- Reports must distinguish engineering smoke results from research-valid conclusions.
- Reports must explicitly document failed hypotheses, limitations, and uncertainty.
