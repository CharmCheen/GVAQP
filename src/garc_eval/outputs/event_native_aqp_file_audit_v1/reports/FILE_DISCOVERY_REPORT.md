# File Discovery Report

**Date:** 2026-06-25
**Source:** `event_native_aqp_file_audit_v1`

---

## 1. Directory Map

| stage directory | exists? | key reports |
|---|---|---|
| `new_video_scout_gate_v1/` (P0) | YES | SCOUT_GATE_REPORT.md, DATASET3_PROTOCOL.md |
| `event_native_aqp_p1_dataset3_semantic_pilot_v1/` (P1) | YES | SEMANTIC_PILOT_REPORT.md, BOUNDARY_DEGENERACY_AUDIT.md |
| `event_native_aqp_p1b_boundary_fix_smoke_v1/` | NOT FOUND (merged into sprint Stage 1) |
| `event_native_aqp_p1c_full_center10_oracle_v1/` | NOT FOUND (merged into sprint Stage 2) |
| `event_native_aqp_autonomous_research_sprint_v1/` (Sprint) | YES | All 9 stages complete |
| `event_native_aqp_overnight_research_sprint_v1/` | NOT FOUND |
| `event_native_aqp_p1c_dataset3_full_center10_oracle_v1/` | NOT FOUND |
| `event_native_aqp_p1_dataset3_semantic_pilot_v1/` | YES |

---

## 2. Directory Counts

| directory | files | size range |
|---|---|---|
| `new_video_scout_gate_v1/` | ~20 files | 500B-100KB |
| `event_native_aqp_p1_dataset3_semantic_pilot_v1/` | ~60 files | 500B-195KB |
| `event_native_aqp_autonomous_research_sprint_v1/` | ~370 files | 200B-500KB |

Total files found: ~450

---

## 3. Key Files Present

### A. P0 Scout Gate (new_video_scout_gate_v1)
- `reports/SCOUT_GATE_REPORT.md` — dataset3=GO, dataset2=WEAK_GO
- `reports/DATASET3_PROTOCOL.md` — frozen experiment plan
- `tables/window_features_dataset3.csv` — 693 5s proxy features
- `tables/summary_combined_full.json` — summary stats

### B. P1 Pilot (event_native_aqp_p1_dataset3_semantic_pilot_v1)
- `reports/SEMANTIC_PILOT_REPORT.md` — 50-anchor VLM pilot
- `reports/P1_DATASET3_SEMANTIC_PILOT_FINAL.md` — DECISION=GO
- `reports/BOUNDARY_DEGENERACY_AUDIT.md` — boundary templated
- `oracle_outputs/dataset3_oracle_parsed.csv` — 50 parsed labels
- `oracle_outputs/pilot_analysis.json` — 10% positive rate

### C. Autonomous Sprint (event_native_aqp_autonomous_research_sprint_v1)
- `state/SPRINT_STATE.json` — COMPLETE, MAINLINE_GO_WITH_BOUNDARY_LIMITATION
- `state/EXPERIMENT_LEDGER.csv` — 9 experiments all DONE
- `state/DECISION_LOG.md` — 6 key decisions
- `state/FAILURE_LOG.md` — 6 failures logged
- `state/NEXT_ACTIONS.md` — 5 priority actions
- `reports/AUTONOMOUS_RESEARCH_SPRINT_FINAL.md` — complete sprint summary
- `reports/STAGE1_BOUNDARY_FIX_SMOKE.md` — boundary fix decision
- `reports/STAGE2_DATASET3_FULL_CENTER10_ORACLE.md` — full oracle reference
- `reports/PROXY_ORACLE_RELATION_ANALYSIS.md` — AUROC=0.624
- `reports/STAGE4_FULL_REFERENCE_AQP_STRUCTURE.md` — 27 clusters
- `reports/BUDGET_REPLAY_AND_ALGORITHM_FINDINGS.md` — best non-oracle methods
- `reports/AQP_ALGORITHM_DESIGN.md` — DCA algorithm
- `reports/RELATED_WORK_BOUNDARY_ANALYSIS.md` — 11-system comparison
- `paper_draft/PAPER_STYLE_RESEARCH_REPORT.md` — full paper draft
- `analysis/full_center10_analysis.json` — numerical analysis
- `analysis/proxy_oracle_relation.csv` — 347-row proxy-oracle data
- `analysis/positive_clusters.csv` — 27 event clusters
- `analysis/selectivity_analysis.csv` — block-level positive rates
- `analysis/temporal_structure.csv` — P(1→1)=0.325
- `analysis/stage1_boundary_scheme_comparison.csv` — boundary smoke results
- `replay/budget_replay_results.csv` — 10 methods x 8 budgets
- `related_work/RELATED_WORK_MATRIX.csv` — 11-system comparison
- `oracle_outputs/dataset3_full_center10_parsed.csv` — 347-row oracle labels
- `oracle_outputs/dataset3_full_center10_raw.jsonl` — raw VLM responses

---

## 4. Stages / Directories Not Found

| expected path | status | notes |
|---|---|---|
| `event_native_aqp_p1b_boundary_fix_smoke_v1/` | NOT FOUND (merged) | Boundary fix executed as Sprint Stage 1, not standalone |
| `event_native_aqp_p1c_full_center10_oracle_v1/` | NOT FOUND (merged) | Full oracle executed as Sprint Stage 2 |
| `event_native_aqp_overnight_research_sprint_v1/` | NOT FOUND | Planned but never separated; all work in single sprint |

---

## 5. What Was NOT Found

- No `plans/` directory within the sprint output (empty directory exists)
- No `tables/` directory within sprint output (empty directory exists)
- No `figures/` directory populated with actual figures within sprint output (empty)
- No JSONL for the full oracle within the sprint (it was written but consumed by analysis)
- No certificate/audit simulation results (not yet implemented)
- No DCA replay results (E1 pending)
- No second-video evaluation beyond dataset3

---

## 6. Stages That May Be Incomplete

| stage | completeness | evidence |
|---|---|---|
| P0 scout | COMPLETE | dataset3 analyzed, GO decision made |
| P1 pilot | COMPLETE | 50 anchors labeled, GO decision with boundary caveat |
| P1b boundary fix | COMPLETE (as Sprint S1) | 3 schemes tested, decision made to use clip-level labels |
| P1c full center10 | COMPLETE (as Sprint S2) | 347 anchors labeled, 40 positives |
| Full-reference AQP analysis | COMPLETE (as Sprint S4) | Selectivity, temporal, clusters analyzed |
| Budget replay | COMPLETE (as Sprint S5) | 10 methods x 8 budgets, 200 random repeats |
| Algorithm exploration | COMPLETE (as Sprint S6) | DCA, CFA, TSA proposed |
| Related work boundary | COMPLETE (as Sprint S7) | 11 systems compared |
| Paper draft | COMPLETE (as Sprint S9) | Full paper-style report generated |

---

## 7. Core Evidence Files for Reading

| priority | file | content |
|---|---|---|
| 1 | `analysis/full_center10_analysis.json` | Full numerical oracle analysis |
| 2 | `replay/budget_replay_results.csv` | 10 methods x 8 budgets |
| 3 | `analysis/proxy_oracle_relation.csv` | 347-row proxy-oracle relationship |
| 4 | `analysis/positive_clusters.csv` | 27 event clusters |
| 5 | `analysis/selectivity_analysis.csv` | Block-level positive rate |
| 6 | `analysis/temporal_structure.csv` | P(1→1)=0.325 |
| 7 | `state/SPRINT_STATE.json` | Sprint state summary |
| 8 | `paper_draft/PAPER_STYLE_RESEARCH_REPORT.md` | Paper draft |
| 9 | `related_work/RELATED_WORK_MATRIX.csv` | 11-system comparison |

---

## 8. Summary

- **3 main output directories** found with complete stage-by-stage results
- **~450 total files** discovered, of which ~35 are critical
- **No p1b/p1c standalone directories** — those stages were executed inside the sprint
- **No certificate simulation** — this is pending (next action E3)
- **No DCA replay** — this is pending (next action E1)
- **All stages through paper draft are complete**
