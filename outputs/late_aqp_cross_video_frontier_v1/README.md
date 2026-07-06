# Cross-Video Validation of Limited-Oracle LATE-AQP Frontier

Second video: `long_video_dataset3` (dataset3).

This directory reproduces the same limited-oracle frontier that was run on realcartest,
using existing full-VLM labels and prior scores only. No new VLM/API calls, no new labels,
no algorithm changes, no tuning.

## Key outputs

- `input_manifest.csv` - candidate video inventory
- `second_video_discovery_report.md` - why dataset3 was selected
- `full_vlm_reference_audit.md` - reference quality audit
- `oracle_replay_isolation_audit.md` - strict_replay vs posthoc_eval classification
- `budget_grid.md` - evaluated budgets per segment
- `cross_video_frontier_raw.csv` - per-seed raw replay rows
- `cross_video_b90_90.csv` - first budget reaching 90/90 per segment/method
- `cross_video_precision_recall_frontier.csv` - mean precision/recall frontier
- `cross_video_macro_micro_summary.csv` - aggregated macro/micro metrics
- `cross_video_failure_taxonomy.csv` - low-budget failure taxonomy
- `cross_video_oracle_usage_report.md` - oracle call accounting
- `comparison_with_realcartest.md` - cross-video pattern comparison
- `FINAL_REPORT.md` - answers to the 10 required questions

## Run

```bash
bash outputs/late_aqp_cross_video_frontier_v1/commands.sh
```
