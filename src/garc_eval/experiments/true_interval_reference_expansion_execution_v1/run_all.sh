#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/build_review_queue.py
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/export_review_clips.py
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/build_contact_sheets.py
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/validate_review_sheet.py
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/merge_human_review.py
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/final_report.py
