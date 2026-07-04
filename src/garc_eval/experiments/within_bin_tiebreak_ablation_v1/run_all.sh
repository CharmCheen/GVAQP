#!/usr/bin/env bash
set -euo pipefail
cd /qiuyeqing/llama_prl/G-ARC
python src/garc_eval/experiments/within_bin_tiebreak_ablation_v1/run_all.py
