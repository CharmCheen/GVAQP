"""T033b-0 — proxy-only start-router (strict-replay LOSO).

Trains a classifier to predict the best full-policy (from {B7, D3, EventLift-DC,
ECP-c2}) for each (segment, budget) cell, using ONLY segment-level proxy statistics
(zero oracle calls). Evaluated via leave-one-segment-out (LOSO).

Training targets: T033a oracle router labels (which policy has best recall per cell).
Features: proxy entropy, Gini, zero_proxy_share, top-k mass, temporal concentration,
          budget_ratio — all computable without oracle calls.
Evaluation: predicted policy's known recall on held-out segment.

If proxy-only router achieves >= 0.200 macro recall (capturing ~56% of oracle lift),
a warmup-router (T033b-1) may not be needed.

Outputs:
  outputs/ecp_event_coverage_policy_v1/t033b0_router_predictions.csv
  outputs/ecp_event_coverage_policy_v1/t033b0_router_loso.csv
  outputs/ecp_event_coverage_policy_v1/t033b0_router_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import SEGMENTS, BUDGET_RATIOS, PROXY_COL, load_segment_data  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

POLICY_POOL = ["B7", "D3", "EventLift-DC", "ECP-c2"]


def compute_segment_features(seg_id, seg_dict):
    """Compute proxy-only features for a segment. No oracle calls."""
    grid, ref_seg, err = load_segment_data(seg_dict)
    if grid is None:
        return None

    proxies = grid[PROXY_COL].values.astype(float)
    n_bins = len(proxies)

    # Basic stats
    mean_p = np.mean(proxies)
    std_p = np.std(proxies)
    max_p = np.max(proxies)
    min_p = np.min(proxies)

    # Zero-proxy share
    zero_p_share = np.mean(proxies == 0.0)
    n_zero = int(np.sum(proxies == 0.0))

    # Proxy entropy (binned)
    hist, _ = np.histogram(proxies, bins=10, range=(0, max(1e-6, max_p)))
    hist = hist / max(1, hist.sum())
    entropy = -np.sum(hist * np.log(hist + 1e-9))

    # Gini coefficient
    sorted_p = np.sort(proxies)
    n = len(sorted_p)
    cumsum = np.cumsum(sorted_p)
    gini = (2 * np.sum((np.arange(1, n + 1) * sorted_p)) - (n + 1) * np.sum(sorted_p)) / (n * np.sum(sorted_p) + 1e-9)

    # Top-k proxy mass
    sorted_desc = np.sort(proxies)[::-1]
    total_mass = max(1e-9, np.sum(sorted_desc))
    top1_mass = sorted_desc[0] / total_mass
    top5_k = min(5, n)
    top5_mass = np.sum(sorted_desc[:top5_k]) / total_mass
    top10_k = min(10, n)
    top10_mass = np.sum(sorted_desc[:top10_k]) / total_mass

    # Proxy concentration (ratio of max to mean)
    concentration = max_p / (mean_p + 1e-9)

    # Temporal concentration: std of proxy across time bins
    # Split segment into thirds
    third = n // 3
    if third > 0:
        p1 = np.mean(proxies[:third])
        p2 = np.mean(proxies[third:2*third])
        p3 = np.mean(proxies[2*third:])
        temporal_std = np.std([p1, p2, p3])
    else:
        temporal_std = 0.0

    # Largest zero-proxy gap (consecutive zero-proxy bins)
    zp_streak = 0
    max_zp_gap = 0
    for p in proxies:
        if p == 0:
            zp_streak += 1
            max_zp_gap = max(max_zp_gap, zp_streak)
        else:
            zp_streak = 0

    # Proxy autocorrelation (lag-1)
    if n > 1:
        autocorr = np.corrcoef(proxies[:-1], proxies[1:])[0, 1]
    else:
        autocorr = 0

    # Number of proxy modes (peaks)
    above_mean = proxies > mean_p
    transitions = np.sum(np.diff(above_mean.astype(int)) != 0) // 2
    n_modes = max(1, int(transitions))

    # Mean proxy gap (average distance between non-zero proxy bins)
    nonzero_indices = np.where(proxies > 0)[0]
    if len(nonzero_indices) > 1:
        gaps = np.diff(nonzero_indices)
        mean_gap = np.mean(gaps)
    else:
        mean_gap = n  # large gap if only one non-zero bin

    return {
        "segment_id": seg_id,
        "n_bins": n_bins,
        "proxy_mean": mean_p, "proxy_std": std_p,
        "proxy_max": max_p, "proxy_min": min_p,
        "zero_proxy_share": zero_p_share, "n_zero_proxy": n_zero,
        "proxy_entropy": entropy, "proxy_gini": gini,
        "top1_mass": top1_mass, "top5_mass": top5_mass, "top10_mass": top10_mass,
        "proxy_concentration": concentration,
        "temporal_proxy_std": temporal_std, "proxy_autocorr": autocorr,
        "n_modes": n_modes, "max_zp_gap": max_zp_gap,
        "mean_proxy_gap": mean_gap,
    }


def load_training_labels():
    """Load oracle router labels from T033a — best policy per (segment, budget)."""
    df = pd.read_csv(OUT / "t033a_router_ceiling.csv")
    labels = {}
    for _, r in df.iterrows():
        labels[(r["segment_id"], r["budget_ratio"])] = r["best_policy"]
    return labels


def load_policy_recall_table():
    """Build a table of each policy's recall per (segment, budget)."""
    hts = pd.read_csv(REPO_ROOT / "outputs/hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv")
    c2 = pd.read_csv(OUT / "t028e1_loso_frontier.csv")

    rows = []
    # B7, D3, EventLift-DC from hts
    hts_map = {"B7-strict-replay": "B7", "D3-norepair-core-strict": "D3",
               "EventLift-discover-certify": "EventLift-DC"}
    for mid, label in hts_map.items():
        sub = hts[hts["method_id"] == mid]
        agg = sub.groupby(["segment_id", "budget_ratio"]).agg(
            recall=("event_recall", "mean")).reset_index()
        agg["policy"] = label
        rows.append(agg)

    # ECP-c2 from LOSO
    c2_sub = c2[c2["variant"] == "c2_loso"]
    c2_agg = c2_sub.groupby(["held_out_segment", "budget_ratio"]).agg(
        recall=("event_recall", "mean")).reset_index()
    c2_agg["segment_id"] = c2_agg["held_out_segment"]
    c2_agg["policy"] = "ECP-c2"
    rows.append(c2_agg[["segment_id", "budget_ratio", "recall", "policy"]])

    return pd.concat(rows, ignore_index=True)


def main():
    # --- 1. Compute features ---
    all_seg_ids = [s["segment_id"] for s in SEGMENTS]
    feature_rows = []
    for seg_dict in SEGMENTS:
        feat = compute_segment_features(seg_dict["segment_id"], seg_dict)
        if feat:
            feature_rows.append(feat)
    features_df = pd.DataFrame(feature_rows)

    # --- 2. Load labels and recall table ---
    labels = load_training_labels()
    recall_table = load_policy_recall_table()

    # Build training data: for each (segment, budget), features + label
    train_rows = []
    for seg in all_seg_ids:
        seg_feat = features_df[features_df["segment_id"] == seg]
        if len(seg_feat) == 0:
            continue
        for br in BUDGET_RATIOS:
            label = labels.get((seg, br), "B7")
            if label not in POLICY_POOL:
                continue  # skip cells where oracle picks a non-pool policy
            row = seg_feat.iloc[0].to_dict()
            row["budget_ratio"] = br
            row["best_policy"] = label
            train_rows.append(row)
    train_df = pd.DataFrame(train_rows)

    # Feature columns
    feature_cols = [c for c in train_df.columns
                    if c not in ("segment_id", "best_policy", "budget_ratio")]
    # Add budget_ratio as feature
    feature_cols = ["budget_ratio"] + [c for c in feature_cols if c != "budget_ratio"]

    # --- 3. LOSO evaluation ---
    results = []
    all_predictions = []

    for held_out_seg in all_seg_ids:
        # Split
        train_mask = train_df["segment_id"] != held_out_seg
        test_mask = train_df["segment_id"] == held_out_seg
        train_data = train_df[train_mask]
        test_data = train_df[test_mask]

        if len(train_data) < 3 or len(test_data) == 0:
            continue

        X_train = train_data[feature_cols].values
        y_train = train_data["best_policy"].values
        X_test = test_data[feature_cols].values

        # Scale
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        # Train
        model = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42)
        model.fit(X_train_s, y_train)

        # Predict
        preds = model.predict(X_test_s)
        probs = model.predict_proba(X_test_s)

        for i, (_, test_row) in enumerate(test_data.iterrows()):
            seg = test_row["segment_id"]
            br = test_row["budget_ratio"]
            predicted_policy = preds[i]
            oracle_policy = test_row["best_policy"]

            # Get predicted policy's recall on this cell
            pr = recall_table[(recall_table["segment_id"] == seg)
                              & (abs(recall_table["budget_ratio"] - br) < 0.001)
                              & (recall_table["policy"] == predicted_policy)]
            predicted_recall = pr["recall"].values[0] if len(pr) else 0.0

            # Get oracle policy's recall
            op = recall_table[(recall_table["segment_id"] == seg)
                              & (abs(recall_table["budget_ratio"] - br) < 0.001)
                              & (recall_table["policy"] == oracle_policy)]
            oracle_recall = op["recall"].values[0] if len(op) else 0.0

            # Also get B7 baseline recall for comparison
            b7 = recall_table[(recall_table["segment_id"] == seg)
                              & (abs(recall_table["budget_ratio"] - br) < 0.001)
                              & (recall_table["policy"] == "B7")]
            b7_recall = b7["recall"].values[0] if len(b7) else 0.0

            results.append({
                "held_out_segment": seg, "budget_ratio": br,
                "predicted_policy": predicted_policy,
                "oracle_policy": oracle_policy,
                "predicted_recall": predicted_recall,
                "oracle_recall": oracle_recall,
                "b7_recall": b7_recall,
                "correct": predicted_policy == oracle_policy,
            })
            all_predictions.append({
                "held_out": seg, "budget": br,
                "predicted": predicted_policy, "oracle": oracle_policy,
                "correct": predicted_policy == oracle_policy,
            })

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUT / "t033b0_router_loso.csv", index=False)
    preds_df = pd.DataFrame(all_predictions)
    preds_df.to_csv(OUT / "t033b0_router_predictions.csv", index=False)

    # --- 4. Report ---
    macro_pred = results_df["predicted_recall"].mean()
    macro_b7 = results_df["b7_recall"].mean()
    accuracy = results_df["correct"].mean()
    n_cells = len(results_df)

    # Per-policy confusion
    confusion = {}
    for pol in POLICY_POOL:
        confusion[pol] = {p: 0 for p in POLICY_POOL}
    for _, row in results_df.iterrows():
        if row["oracle_policy"] in POLICY_POOL:
            confusion[row["oracle_policy"]][row["predicted_policy"]] += 1

    L = []
    L.append("# T033b-0 — Proxy-only start-router (LOSO)\n")
    L.append(
        "Trains a RandomForest classifier to predict the best full-policy for each "
        "(segment, budget) cell using ONLY segment-level proxy statistics. "
        "No oracle calls consumed by the router. Evaluated via leave-one-segment-out.\n"
    )
    L.append(f"Policy pool: {', '.join(POLICY_POOL)}\n")

    L.append(f"## Results\n")
    L.append(f"- **Learned router macro recall**: {macro_pred:.3f}")
    L.append(f"- **B7 baseline macro recall**: {macro_b7:.3f}")
    L.append(f"- **Router lift over B7**: {macro_pred - macro_b7:+.3f}")
    L.append(f"- **Router accuracy** (matching oracle): {accuracy*100:.1f}% ({int(results_df['correct'].sum())}/{n_cells})")
    L.append(f"- **Oracle ceiling (T033a)**: 0.228")
    oracle_lift_captured = (macro_pred - macro_b7) / max(0.001, 0.228 - macro_b7) * 100
    L.append(f"- **Oracle lift captured**: {oracle_lift_captured:.1f}%\n")

    L.append("## Per-cell predictions\n")
    L.append("| held_out | budget | predicted | oracle | correct | pred_recall | oracle_recall |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in results_df.iterrows():
        mark = "YES" if r["correct"] else "no"
        L.append(f"| {r['held_out_segment']} | {r['budget_ratio']:.2f} | {r['predicted_policy']} | {r['oracle_policy']} | {mark} | {r['predicted_recall']:.3f} | {r['oracle_recall']:.3f} |")

    L.append("\n## Policy confusion matrix (oracle → predicted)\n")
    L.append("| oracle \\ predicted | " + " | ".join(POLICY_POOL) + " |")
    L.append("| " + " | ".join(["-"] * (1 + len(POLICY_POOL))) + " |")
    for pol in POLICY_POOL:
        cells = [str(confusion[pol].get(p, 0)) for p in POLICY_POOL]
        L.append(f"| {pol} | " + " | ".join(cells) + " |")

    L.append(f"\n## Verdict\n")
    if macro_pred >= 0.200:
        L.append(f"- **PASS**: router achieves {macro_pred:.3f} >= 0.200 target, capturing {oracle_lift_captured:.0f}% of oracle lift.")
        L.append("  Proxy-only features are sufficient; warmup may not be needed.")
    elif macro_pred >= 0.180:
        L.append(f"- **PARTIAL**: router achieves {macro_pred:.3f}, between B7 ({macro_b7:.3f}) and target 0.200.")
        L.append("  Some oracle lift captured. Warmup-router (T033b-1) may improve further.")
    else:
        L.append(f"- **FAIL**: router ({macro_pred:.3f}) barely exceeds B7 ({macro_b7:.3f}).")
        L.append("  Proxy-only features insufficient. Warmup-router (T033b-1) is needed.")

    # Feature importance
    L.append("\n## Top feature importances\n")
    importances = model.feature_importances_
    sorted_idx = np.argsort(-importances)[:10]
    for idx in sorted_idx:
        L.append(f"- {feature_cols[idx]}: {importances[idx]:.4f}")

    md = OUT / "t033b0_router_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't033b0_router_loso.csv'}")
    print(f"wrote {OUT / 't033b0_router_predictions.csv'}")
    print(f"wrote {md}")

    print(f"\n=== T033b-0 Proxy-only Start-Router ===")
    print(f"Router macro recall: {macro_pred:.3f}")
    print(f"B7 baseline:         {macro_b7:.3f}")
    print(f"Oracle ceiling:      0.228")
    print(f"Lift over B7:        {macro_pred - macro_b7:+.3f}")
    print(f"Accuracy:            {accuracy*100:.1f}%")
    print(f"Oracle lift captured: {oracle_lift_captured:.1f}%")


if __name__ == "__main__":
    main()
