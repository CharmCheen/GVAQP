# Resume Status: roadclip_budget_v2 VLM Oracle Expanded

- Checked at: 2026-06-15T01:26:48.233950+00:00
- Workspace: `/qiuyeqing/llama_prl/G-ARC/test_vlm`
- Output dir: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded`

## Running Processes
- No existing related VLM/expanded benchmark process detected.

## Inputs
- clips.csv: exists, rows=1000, unique_clip_id=1000
- proxy_scores.csv: exists, rows=1000, unique_clip_id=1000, covers_all_clips=True; score_count=exists, na=0, score_naive=exists, na=0, score_kinematic=exists, na=0
- tracks.csv: exists, rows=655261, unique_clip_id=997

## VLM Labels
- vlm_labels_conservative.csv: exists, rows=154, unique_clip_id=154, target=1000, missing=846
- status distribution: `{'ok': 154}`
- conservative_positive distribution: `{'no': 144, 'yes': 10}`
- non-ok / failed / parse-error rows: 0

## Benchmark Outputs
- final_vlm_oracle_acceleration_report.md: exists=False, size=None
- vlm_oracle_budget_curve.csv: exists=False, size=None
- target_recall_cost_saving.csv: exists=False, size=None

## Status
- BLOCKED_INCOMPLETE_VLM_LABELS: 154/1000 labeled.

## Resume Update

- 2026-06-15 UTC: Foreground VLM resume validated checkpoint behavior and advanced labels to 197/1000.
- `tmux` was installed because it was not present on the machine.
- The foreground VLM process was stopped after checkpoint persistence, then restarted in tmux session `roadclip_vlm_expanded`.
- tmux resume command started from `existing=197 pending=803`; no second 32B VLM process was left running.
- tmux pane PID recorded in `vlm_resume.pid`; stdout/stderr is tee'd to `vlm_resume.log`.
- The tmux command runs `04_run_conservative_vlm.py` first and, if it exits successfully, automatically runs `09_vlm_oracle_acceleration_benchmark.py`.

## Final Resume Result

- Completed at: 2026-06-15 UTC.
- Existing VLM process duplication check: no related VLM or benchmark process remained after completion.
- Compile validation: `python -m py_compile experiments/roadclip_budget_v2/*.py` passed.
- clips.csv: 1000 rows, 1000 unique clip_id.
- proxy_scores.csv: 1000 rows, 1000 unique clip_id.
- tracks.csv: 655261 rows, 997 unique clip_id.
- vlm_labels_conservative.csv: 1000 rows, 1000 unique clip_id, status distribution `{'ok': 1000}`.
- VLM pseudo-oracle positives: 61 / 1000 = 0.061.
- Generated outputs:
  - `proxy_scores_with_learned.csv`
  - `vlm_oracle_budget_curve_raw.csv`
  - `vlm_oracle_budget_curve.csv`
  - `target_recall_cost_saving.csv`
  - `vlm_oracle_budget_curve.png`
  - `final_vlm_oracle_acceleration_report.md`
- Final status: PASS_VLM_ORACLE_ACCELERATION.
