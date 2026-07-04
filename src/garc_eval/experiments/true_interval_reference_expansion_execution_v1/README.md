# true_interval_reference_expansion_execution_v1

Build a human review package for expanding the true interval reference. This package does not call VLM, LLM, YOLO, CLIP, tracking, motion proxy, or any model.

Run:

```bash
bash src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/run_all.sh
```

Human workflow:

1. Open `src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/human_review_sheet.csv` or `.xlsx`.
2. Review media under `review_media/` when available.
3. Fill human fields only.
4. Validate:

```bash
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/validate_review_sheet.py --sheet src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/human_review_sheet.csv
```

5. Merge:

```bash
python src/garc_eval/experiments/true_interval_reference_expansion_execution_v1/merge_human_review.py
```
