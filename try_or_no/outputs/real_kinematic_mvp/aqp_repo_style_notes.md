# AQP Repo Style Notes: Design Choices to Copy

## SUPG MVP Structure

**Input format:** Compact CSV with `id, label, proxy_score`. Labels are precomputed oracle boolean predicates. Proxy scores are cheap approximations from a lightweight model.

**Key design choices:**
1. **Compact table interface:** All data lives in one CSV. No runtime data loading from images/video.
2. **Precomputed oracle labels:** The expensive predicate evaluation is done once offline. The MVP only reads labels.
3. **Budgeted sampling:** `budget` parameter controls how many oracle labels are inspected. The returned *set* can be larger than the budget.
4. **Repeated trials:** `TrialRunner` runs N trials with different seeds, reports mean ± std.
5. **Budget-quality curves:** Sweep budget from small to large, plot precision/recall vs budget.
6. **Clear baselines:** Uniform, naive, importance sampling — all in the same framework.
7. **Metrics CSV:** Results saved as CSV with columns for method, budget, seed, precision, recall, coverage, size.

**What we copy:**
- Compact CSV table as the core data interface
- Precomputed oracle states/labels from real annotations
- Budget sweep with repeated seeds
- Strong baseline comparison in the same framework
- Metrics CSV output

## ABae MVP Structure

**Input format:** CSV with `proxy_scores, statistics, predicates`. Predicates are boolean oracle labels. Statistics are the aggregation target (e.g., distance, count).

**Key design choices:**
1. **Two-phase sampling:** Phase 1 (pilot) estimates per-stratum stats. Phase 2 allocates remaining budget optimally.
2. **Optimal allocation:** Budget allocated proportional to `sqrt(p_i) * sigma_i` — accounts for both predicate frequency and statistic variance.
3. **CI via bootstrap:** Confidence intervals computed via bootstrap resampling of the reservoir.
4. **MSE evaluation:** Mean squared error across repeated trials at each budget level.
5. **Sensitivity analysis:** Vary K (strata), C (budget split), and other hyperparameters.

**What we copy:**
- Two-phase pilot + allocation pattern
- MSE / MAE evaluation across trials
- Bootstrap CI where applicable
- Sensitivity to hyperparameters (tau, K, etc.)

## Design Choices for Our Kinematic MVP

**Same compact table interface:** One CSV per experiment with precomputed oracle states and labels.

**Oracle states from real annotations:** For UA-DETRAC: bounding boxes and track IDs from real annotations. For KITTI: ego pose from OXTS data. No synthetic trajectories as main data.

**Budget = oracle call count:** Each method's cost is measured by how many frames it calls the oracle (reads the annotation).

**Clip construction from oracle labels:** Ground-truth clips are contiguous runs of frames where the predicate holds for >= tau frames.

**Baselines in the same framework:** All methods (B0-B9) produce frame-level predicate predictions from which clips are constructed. Same metrics, same table.

**Metrics CSV + report:** Per-method, per-query, per-budget, per-seed metrics in CSV. Summary report with honest assessment.
