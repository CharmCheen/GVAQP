#!/usr/bin/env bash
set -euo pipefail

cd /qiuyeqing/llama_prl/G-ARC/test_vlm
source /qiuyeqing/llama_prl/G-ARC/env_garc.sh

python focused_validation_outputs/scripts/focused_validation.py \
  --output_dir focused_validation_outputs
