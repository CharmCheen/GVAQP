# Input Inventory — GLM-4.1V Held-Out Validation & Cascade Simulation

**Date**: 2026-06-26
**Output directory**: `garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/`

---

## 1. Best Prompts

| File | Status | Description |
|------|--------|-------------|
| `prompts/BEST_glm_final.md` | EXISTS | GLM best (v1_lower_threshold), tuning F1=0.706 on GLM test set |
| `prompts/BEST_qwen_final.md` | EXISTS | Qwen best (v3_two_step), tuning F1=0.571 on Qwen test set |

Both prompts are frozen. No new prompt tuning will be performed.

---

## 2. Test Sets (Held-Out for GLM)

| File | N | Pos | Neg | Status | Notes |
|------|---|---|-----|--------|-------|
| `test_sets/qwen_test_small.csv` | 10 | 2 | 8 | EXISTS | Phase 1 gate — held-out Qwen test set |
| `test_sets/qwen_test_set.csv` | 36 | 2 | 34 | EXISTS | Larger Qwen test set (includes small set) |
| `test_sets/glm_test_small.csv` | 15 | 10 | 5 | EXISTS | GLM tuning set (NOT held-out) |
| `test_sets/glm_test_set.csv` | 38 | 19 | 19 | EXISTS | Larger GLM test set |

**Key**: `qwen_test_small.csv` is the GLM held-out gate. GLM was tuned on `glm_test_small.csv` (disjoint sample set).

---

## 3. Pilot 123-Sample Data

| File | Status | Notes |
|------|--------|-------|
| `pilot/inputs/sample_manifest_paired.csv` | EXISTS | 120 paired samples + 12 smoke = 132 total entries |
| `pilot/inputs/contact_sheets/*.jpg` | EXISTS | 123 contact sheets built |
| `pilot/tables/paired_predictions.csv` | EXISTS | Old GLM v0 + Qwen outputs (123 rows, 106 valid pairs) |
| `pilot/tables/qwen32b_paired_results.csv` | EXISTS | Qwen paired results |
| `pilot/tables/glm41v_paired_results.csv` | EXISTS | GLM paired results |
| `pilot/reports/GLM41V_QWEN32B_ORACLE_COMPARISON.md` | EXISTS | Old pilot report (GLM NOT USEFUL with v0 prompt) |

**Important**: Old pilot used GLM v0_original prompt (0% recall). The BEST prompt (v1_lower_threshold, 60% GLM tuning recall) is the one being evaluated now.

---

## 4. Qwen Reference Labels

| Source | Status | Notes |
|--------|--------|-------|
| `canonical_dataset3_anchor_table.csv` | EXISTS | 347 anchors, 40 reference positives, full proxy features |
| `pilot/tables/paired_predictions.csv` | EXISTS | Qwen labels from pilot rerun (OLD prompt, not BEST_qwen_final) |
| V13.8 oracle labels | EXISTS (embedded in canonical table) | Qwen3-VL-32B labels are the reference |

**Qwen reference exists. No new Qwen calls will be made.**

The ground truth in all test CSVs (`qwen_test_small.csv`, `qwen_test_set.csv`) is derived from the canonical dataset3 anchor table, which uses Qwen3-VL-32B as the reference oracle.

---

## 5. Proxy / AQP Features

Available in `canonical_dataset3_anchor_table.csv`:

| Feature | Status | Use |
|---------|--------|-----|
| `object_count_mean` | EXISTS | Best single-feature proxy (AUC 0.738) |
| `score_fusion_geometry_motion` | EXISTS | Composite proxy score |
| `score_yolo_count` | EXISTS | YOLO count score |
| `score_motion` | EXISTS | Motion score |
| `motion_energy_mean` | EXISTS | Raw motion feature |
| `event_cluster_id` | EXISTS | Event cluster assignment |
| `is_singleton_cluster` | EXISTS | Singleton event flag |
| `is_positive` | EXISTS | Oracle label (Qwen reference) |
| `anchor_id` | EXISTS | Anchor identifier |
| `L3 rank` | CAN BE COMPUTED | Rank by proxy score descending |

**Missing for cascade**:
- `cold-block flag` — NOT explicitly in canonical table, can be derived from temporal gaps
- `L3 selected flags` — NOT pre-computed, can be derived from L3 budget selection

---

## 6. Model Availability

| Model | Path | Status |
|-------|------|--------|
| GLM-4.1V-9B | `/models/vlm/GLM-4.1V/` | EXISTS (4 shards, ~18 GB) |
| Qwen3-VL-32B | `/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct/` | EXISTS |
| Qwen3-VL-8B | `/models/vlm/qwen3_vl/Qwen3-VL-8B-Instruct/` | EXISTS |

GPU: NVIDIA A800-SXM4-80GB (79.3 GB), fits both models individually.

---

## 7. Scripts

| Script | Status | Notes |
|--------|--------|-------|
| `prompt_sweep_fast.py` | EXISTS | Runs one model+prompt on a test CSV |
| `build_small_test.py` | EXISTS | Build test sets |
| `cascade_simulation.py` (pilot) | EXISTS | Old cascade simulation (can adapt) |

---

## 8. Gap Analysis

| What | Status | Action |
|------|--------|--------|
| Qwen reference | EXISTS | Reuse directly |
| GLM on qwen_test_small with BEST prompt | MISSING | Run Phase 1 |
| GLM on 123 pilot with BEST prompt | MISSING | Run Phase 2 (only if gate passes) |
| Cascade simulation with NEW GLM outputs | MISSING | Run Phase 3 (only if GLM useful) |
| Theoretical analysis report | MISSING | Phase 4 |

---

## 10. Phase 3 Candidate Pool Determination

| Parameter | Value | Source |
|-----------|-------|--------|
| Candidate pool | 123-sample pilot | `paired_predictions.csv` (123 entries from dataset3) |
| N (effective) | 122 | 1 parse error excluded |
| Qwen positives in pool | 40 | canonical dataset3 is_positive column |
| Qwen negatives in pool | 82 | 83 total - 1 parse error |
| Event clusters | 27 | From event_cluster_id column |
| Singleton clusters | 21 | From is_singleton_cluster column |
| Mapped to dataset3 347-anchor | 123/123 (100%) | All anchors found in canonical table |
| Unmapped anchors | 0 | — |
| Overlap with 10-sample test set | 10/10 (100%) | All test anchors in pilot |
| **Overlap with GLM tuning set** | **15/15 (100%)** | All 15 GLM tuning anchors are in 123-pilot (12.2% of pilot) |
| **Overlap with Qwen tuning set** | **10/10 (100%)** | All 10 Qwen tuning anchors are in 123-pilot (8.1% of pilot) |
| **Combined tuning overlap** | **23/123 (18.7%)** | 23 unique anchors overlap; 52.2% Qwen-positive rate in overlap |
| Non-overlapping test anchors | 0 | — |

**Rationale for using N=123 pilot itself**: The 123-sample pilot is the set for which both GLM outputs and Qwen reference labels exist. Expanding to full dataset3 347-anchor would require missing GLM labels for 224 anchors. Since the task prohibits new large-scale inference without explicit authorization, and the existing GLM coverage is complete for the pilot, N=123 is used as the Phase 3 candidate pool.

**⚠️ OVERLAP_MATERIAL_RESULT_INVALID**: 18.7% of the 123-pilot overlaps with prompt tuning sets. All Phase 2/3 absolute metrics (61.5% positive bin rate, 60% recall, +45pp lift) are upper bounds inflated by tuning set familiarity. Sensitivity check on N=100 clean pilot shows ~4.4pp inflation. Directional finding (GLM > L3) survives; absolute numbers should carry an "upper bound" caveat. See CORRECTIONS.md for full audit.

**Budget points for Phase 3**: B = 30, 40, 60, 80, 100. B=150 excluded (B > N=123).

---

## 11. Final State (After All Phases)

| What | Status |
|------|--------|
| Phase 0 Inventory | Complete |
| Phase 1 Gate | PASS (10-sample, 2/2 Qwen-pos covered) |
| Phase 2 Pilot | Complete (123 GLM calls, 122 valid, 1 parse error) |
| Phase 3 Cascade | Complete (7 strategies × 500 seeds on N=123) |
| Phase 4 Theory | Complete (finite-population certificate framework) |
| GLM calls made | 123 total |
| Qwen calls made | 0 (all reference reused) |
| Final decision | `USE_GLM_AS_BOOSTER` |
