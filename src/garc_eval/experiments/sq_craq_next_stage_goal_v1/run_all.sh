#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

python src/garc_eval/experiments/sq_craq_next_stage_goal_v1/cils_vs_topk_value_add_audit.py
python src/garc_eval/experiments/sq_craq_next_stage_goal_v1/audited_interval_envelope_mvp.py
python src/garc_eval/experiments/sq_craq_next_stage_goal_v1/true_interval_reference_expansion_pack.py
python src/garc_eval/experiments/sq_craq_next_stage_goal_v1/drivingdojo_signal_probe_scaffold.py
python src/garc_eval/experiments/sq_craq_next_stage_goal_v1/final_handoff.py
