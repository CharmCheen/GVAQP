# Repository Audit for Codex — /qiuyeqing/llama_prl/G-ARC

**Generated:** 2026-06-23
**Scope:** Read-only inventory of all research outputs, experiments, reports, tables, scripts, and decisions.

## Files in this package

| File | Description |
|---|---|
| `ARTIFACT_INVENTORY.md` | Per-experiment catalog with goals, inputs, scripts, reports, tables, decisions |
| `EXPERIMENT_LINEAGE.md` | Chronological dependency chain, what each experiment consumed/produced |
| `KEY_RESULTS_TABLE.csv` | Quantitative metrics from all experiments, one row per metric |
| `DECISION_LOG.md` | All extracted final decision strings with validity assessment |
| `EVIDENCE_PACK.md` | Research-facing summary: what's validated, what's failed, what's uncertain |
| `OPEN_QUESTIONS_AND_RISKS.md` | Methodological, metric, dataset, oracle, and AQP risks |
| `CODEX_ANALYSIS_PROMPT.md` | Self-contained prompt for another model to analyze the project |
| `manifest_files.csv` | File-level inventory with paths, roles, experiment IDs |
| `README.md` | This file |

## How to use

1. Start with `EVIDENCE_PACK.md` for a quick research-status overview
2. Read `EXPERIMENT_LINEAGE.md` to understand the chronological dependency chain
3. Check `DECISION_LOG.md` for all final decisions and which are still valid
4. Use `KEY_RESULTS_TABLE.csv` for quantitative comparisons across experiments
5. Feed `CODEX_ANALYSIS_PROMPT.md` to another model for a fresh analysis

## Key numbers

- **~1,271 files cataloged** (excluding raw VLM responses, models, videos)
- **30+ experiment directories** across test_vlm/outputs and garc_eval/outputs
- **24 distinct decision strings** extracted
- **915 raw VLM responses** across V13.5 (100), V13.6 (416), V13.8 (399)
- **3 protocol documents** (V12.1 master, V13.5 validation, V13.7 replay)

## Important caveats

- All VLM labels are `VLM_ORACLE_RELATIVE`, not human truth
- All V13.x results are single-video (realcartest.mp4, ~66 min)
- The V13.9→V13.10 metric reconciliation confirmed no semantic difference in event-hit definitions
- The active pipeline ended at V13.10 with `ADAPTIVE_NO_BETTER` and `SAME_BASE_HURTS_CONSISTENTLY`
