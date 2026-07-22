# Exact Legal-Partition Ceiling Report

Decision: `MATERIALIZER_HEADROOM_GO`.

Evaluated 738 frozen controlled traces, 8 selector variants, and budgets [np.int64(5), np.int64(10), np.int64(20), np.int64(50), np.int64(80), np.int64(100)]. No acquisition or VLM call was executed.

Selector-macro K3-safe AUC is 0.312704700; the exact legal-partition ceiling is 0.313874314; the gap is +0.001169613.

The frozen headroom requirements are met by 3 non-random selector variants for standard AUC, 3 after excluding the single >40-second reference, 3 under anchor-certified matching, and 5 aggregate budgets. Legality violations: 0. K3-safe reproduces saved metrics with maximum absolute difference 8.33e-17.

All legal ceiling intervals are minimal positive-anchor convex hulls, so boundary contribution is fixed to zero and all gain is attributed to partition decisions. Full per-trace, per-budget, per-selector, anchor-certified, and pathological-reference sensitivity tables accompany this report.
