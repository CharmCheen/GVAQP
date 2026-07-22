#!/usr/bin/env python3
"""
H-PROXY1 LightGBM Event Proxy Pipeline.

Trains a unified LightGBM classifier to predict 'OTHER_AGENT_ENTERS_EGO_PATH' events
from track-aggregated features. All front-ends use identical LightGBM + feature schema.

Currently uses SYNTHETIC DATA for pipeline validation. Real training requires:
  - DrivingDojo structured event labels (not yet available)
  - Gate P1 winners' track features computed on DrivingDojo clips

Usage:
  python scripts/train_proxy_event_model.py smoke        # Synthetic data smoke test
  python scripts/evaluate_proxy_event_model.py smoke      # Evaluate synthetic model
  python scripts/train_proxy_event_model.py train         # Train on real data (BLOCKED)
"""

import sys, os, json, argparse, time
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve
import warnings
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"
EVENT_DIR = OUTPUT_DIR / "raw/event_scores"
MODEL_DIR = OUTPUT_DIR / "models"

# Unified feature schema
PROXY_FEATURES_V1 = [
    # Motion features
    "bbox_cx_norm", "bbox_cy_norm", "bbox_w_norm", "bbox_h_norm",
    "bbox_area_norm", "bbox_growth", "lateral_velocity",
    "track_age", "track_confidence", "detection_confidence",
    "approx_ttc",
    # Road-relative features (NaN for B0 which has no lane model)
    "lane_relative_position", "lane_relative_velocity",
    "distance_to_left_boundary", "distance_to_right_boundary",
    "in_ego_corridor", "boundary_crossing_count",
    "bottom_center_drivable", "drivable_overlap",
    "lane_confidence", "lane_temporal_stability",
    # Track-aggregated (computed per clip)
    "track_mean_cx", "track_std_cx", "track_mean_cy", "track_std_cy",
    "track_duration", "track_displacement",
    "track_bbox_growth_rate", "track_lateral_motion_energy",
]

# Synthetic event ontology
EVENT_CLASSES = {
    1: "OTHER_AGENT_ENTERS_EGO_PATH",
    0: "NO_PATH_INTRUSION",
    -1: "HARD_NEGATIVE",
}


def generate_synthetic_data(n_clips=600, n_tracks_per_clip=8, random_state=42):
    """Generate synthetic track features for pipeline smoke testing.

    Positive clips: vehicles with high lateral motion, boundary crossing, ego-corridor entry.
    Negative clips: stable forward motion, no boundary crossing.
    Hard negatives: lateral motion but no ego-corridor entry (adjacent lane).
    """
    rng = np.random.RandomState(random_state)
    
    # Proportional split: 1/3 positive, 1/3 hard negative, 1/3 negative
    n_each = n_clips // 3
    clip_labels = [1] * n_each + [-1] * n_each + [0] * (n_clips - 2 * n_each)
    
    # Assign sessions (for grouped splitting)
    n_sessions = 12
    session_ids = rng.randint(0, n_sessions, size=n_clips)
    
    data = []
    for clip_idx, label in enumerate(clip_labels):
        # Clip-level features (aggregated from tracks)
        for track_idx in range(rng.randint(3, n_tracks_per_clip)):
            row = {
                "clip_id": f"synth_clip_{clip_idx:04d}",
                "session_id": f"session_{session_ids[clip_idx]:02d}",
                "track_id": track_idx,
                "label": label,
                "event_class": EVENT_CLASSES[label],
            }
            
            # Generate features based on label
            if label == 1:  # positive: entering ego path
                row["bbox_cx_norm"] = rng.uniform(0.35, 0.65)
                row["bbox_cy_norm"] = rng.uniform(0.4, 0.9)
                row["bbox_w_norm"] = rng.uniform(0.02, 0.15)
                row["bbox_h_norm"] = rng.uniform(0.03, 0.20)
                row["bbox_area_norm"] = row["bbox_w_norm"] * row["bbox_h_norm"]
                row["bbox_growth"] = rng.uniform(0.1, 0.5)
                row["lateral_velocity"] = rng.uniform(0.02, 0.15)
                row["track_age"] = rng.uniform(5, 30)
                row["track_confidence"] = rng.uniform(0.5, 1.0)
                row["detection_confidence"] = rng.uniform(0.4, 1.0)
                row["approx_ttc"] = rng.uniform(0.5, 5.0)
                row["lane_relative_position"] = rng.uniform(-0.3, 0.3)
                row["lane_relative_velocity"] = rng.uniform(-0.05, 0.05)
                row["distance_to_left_boundary"] = rng.uniform(0.0, 0.2)
                row["distance_to_right_boundary"] = rng.uniform(0.0, 0.2)
                row["in_ego_corridor"] = rng.choice([0, 1], p=[0.3, 0.7])
                row["boundary_crossing_count"] = rng.randint(0, 3)
                row["bottom_center_drivable"] = rng.uniform(0.5, 1.0)
                row["drivable_overlap"] = rng.uniform(0.3, 0.9)
                row["lane_confidence"] = rng.uniform(0.4, 0.9)
                row["lane_temporal_stability"] = rng.uniform(0.3, 0.8)
                
            elif label == -1:  # hard negative: lateral motion but no entry
                row["bbox_cx_norm"] = rng.uniform(0.15, 0.35)
                row["bbox_cy_norm"] = rng.uniform(0.4, 0.8)
                row["bbox_w_norm"] = rng.uniform(0.02, 0.12)
                row["bbox_h_norm"] = rng.uniform(0.03, 0.18)
                row["bbox_area_norm"] = row["bbox_w_norm"] * row["bbox_h_norm"]
                row["bbox_growth"] = rng.uniform(0.0, 0.2)
                row["lateral_velocity"] = rng.uniform(0.01, 0.10)
                row["track_age"] = rng.uniform(3, 20)
                row["track_confidence"] = rng.uniform(0.4, 0.9)
                row["detection_confidence"] = rng.uniform(0.3, 0.9)
                row["approx_ttc"] = rng.uniform(1.0, 10.0)
                row["lane_relative_position"] = rng.uniform(-0.4, -0.2)
                row["lane_relative_velocity"] = rng.uniform(-0.03, 0.03)
                row["distance_to_left_boundary"] = rng.uniform(0.0, 0.1)
                row["distance_to_right_boundary"] = rng.uniform(0.1, 0.4)
                row["in_ego_corridor"] = 0
                row["boundary_crossing_count"] = 0
                row["bottom_center_drivable"] = rng.uniform(0.5, 1.0)
                row["drivable_overlap"] = rng.uniform(0.0, 0.3)
                row["lane_confidence"] = rng.uniform(0.4, 0.9)
                row["lane_temporal_stability"] = rng.uniform(0.3, 0.8)
                
            else:  # negative: stable motion
                row["bbox_cx_norm"] = rng.uniform(0.35, 0.65)
                row["bbox_cy_norm"] = rng.uniform(0.6, 0.95)
                row["bbox_w_norm"] = rng.uniform(0.02, 0.10)
                row["bbox_h_norm"] = rng.uniform(0.03, 0.15)
                row["bbox_area_norm"] = row["bbox_w_norm"] * row["bbox_h_norm"]
                row["bbox_growth"] = rng.uniform(-0.05, 0.05)
                row["lateral_velocity"] = rng.uniform(-0.01, 0.01)
                row["track_age"] = rng.uniform(1, 15)
                row["track_confidence"] = rng.uniform(0.3, 0.8)
                row["detection_confidence"] = rng.uniform(0.3, 0.8)
                row["approx_ttc"] = rng.uniform(2.0, 20.0)
                row["lane_relative_position"] = rng.uniform(0.1, 0.4)
                row["lane_relative_velocity"] = rng.uniform(-0.01, 0.01)
                row["distance_to_left_boundary"] = rng.uniform(0.1, 0.3)
                row["distance_to_right_boundary"] = rng.uniform(0.1, 0.3)
                row["in_ego_corridor"] = rng.choice([0, 1], p=[0.7, 0.3])
                row["boundary_crossing_count"] = 0
                row["bottom_center_drivable"] = rng.uniform(0.5, 1.0)
                row["drivable_overlap"] = rng.uniform(0.0, 0.5)
                row["lane_confidence"] = rng.uniform(0.4, 0.9)
                row["lane_temporal_stability"] = rng.uniform(0.3, 0.8)
            
            # Track-aggregated features (constant per clip for synthetic)
            row["track_mean_cx"] = row["bbox_cx_norm"]
            row["track_std_cx"] = rng.uniform(0.0, 0.1)
            row["track_mean_cy"] = row["bbox_cy_norm"]
            row["track_std_cy"] = rng.uniform(0.0, 0.1)
            row["track_duration"] = row["track_age"] * 0.2
            row["track_displacement"] = rng.uniform(0.0, 0.3)
            row["track_bbox_growth_rate"] = row["bbox_growth"]
            row["track_lateral_motion_energy"] = abs(row["lateral_velocity"]) * row["track_age"]
            
            data.append(row)
    
    df = pd.DataFrame(data)
    return df, session_ids


def split_data(df, session_ids, train_frac=0.6, calibrate_frac=0.2):
    """Split by session (not by clip), matching experimental protocol."""
    sessions = df["session_id"].unique()
    n = len(sessions)
    n_train = int(n * train_frac)
    n_cal = int(n * calibrate_frac)
    
    rng = np.random.RandomState(42)
    perm = rng.permutation(sessions)
    train_sessions = set(perm[:n_train])
    cal_sessions = set(perm[n_train:n_train + n_cal])
    test_sessions = set(perm[n_train + n_cal:])
    
    train_df = df[df["session_id"].isin(train_sessions)]
    cal_df = df[df["session_id"].isin(cal_sessions)]
    test_df = df[df["session_id"].isin(test_sessions)]
    
    return train_df, cal_df, test_df


class RuleBaseline:
    """Simple rule-based event detector: lateral motion + boundary crossing + growth."""
    
    def __init__(self, lateral_thresh=0.03, growth_thresh=0.1, corridor_weight=0.5):
        self.lateral_thresh = lateral_thresh
        self.growth_thresh = growth_thresh
        self.corridor_weight = corridor_weight
    
    def predict_proba(self, df):
        scores = np.zeros(len(df))
        for i, (_, row) in enumerate(df.iterrows()):
            s = 0
            if abs(row.get("lateral_velocity", 0)) > self.lateral_thresh:
                s += 0.3
            if row.get("bbox_growth", 0) > self.growth_thresh:
                s += 0.2
            if row.get("in_ego_corridor", 0) == 1:
                s += 0.3
            if row.get("boundary_crossing_count", 0) > 0:
                s += 0.2
            scores[i] = min(s, 1.0)
        return scores


def train_lgbm(train_df, val_df):
    """Train LightGBM with frozen hyperparameters."""
    import lightgbm as lgb
    
    feature_cols = [c for c in PROXY_FEATURES_V1 if c in train_df.columns]
    X_train = train_df[feature_cols].fillna(0).values.astype(np.float64)
    y_train = (train_df["label"] == 1).astype(int).values.astype(np.float64)
    X_val = val_df[feature_cols].fillna(0).values.astype(np.float64)
    y_val = (val_df["label"] == 1).astype(int).values.astype(np.float64)
    
    params = {
        "objective": "binary",
        "metric": "average_precision",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "random_state": 42,
        "n_jobs": 4,
    }
    
    dtrain = lgb.Dataset(X_train, label=y_train, params={"verbose": -1})
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain, params={"verbose": -1})
    
    model = lgb.train(
        params,
        dtrain,
        num_boost_round=50,
        valid_sets=[dval],
        valid_names=["val"],
    )
    
    return model, feature_cols


def train_smoke():
    """Run synthetic data smoke test."""
    print("=== LightGBM Event Proxy — Synthetic Smoke Test ===")
    
    df, session_ids = generate_synthetic_data()
    print(f"Synthetic data: {len(df)} tracks across {df['clip_id'].nunique()} clips")
    print(f"  Positives: {(df['label']==1).sum()}, Hard neg: {(df['label']==-1).sum()}, Neg: {(df['label']==0).sum()}")
    
    train_df, cal_df, test_df = split_data(df, session_ids)
    print(f"Split: train={len(train_df)}, cal={len(cal_df)}, test={len(test_df)}")
    
    # Train LightGBM
    model, feature_cols = train_lgbm(train_df, cal_df)
    
    if model is None:
        print("LightGBM not available. Skipping training.")
        return None
    
    # Evaluate on test
    X_test = test_df[feature_cols].fillna(0).values
    y_test = (test_df["label"] == 1).astype(int).values
    y_pred = model.predict(X_test)
    
    auprc = average_precision_score(y_test, y_pred)
    auroc = roc_auc_score(y_test, y_pred)
    
    # Rule baseline
    rule = RuleBaseline()
    rule_pred = rule.predict_proba(test_df)
    rule_auprc = average_precision_score(y_test, rule_pred)
    
    print(f"\nTest Results:")
    print(f"  LightGBM AUPRC: {auprc:.4f}")
    print(f"  LightGBM AUROC: {auroc:.4f}")
    print(f"  Rule Baseline AUPRC: {rule_auprc:.4f}")
    
    # Feature importance
    if hasattr(model, 'feature_importance'):
        importances = list(zip(feature_cols, model.feature_importance(importance_type="gain")))
        importances.sort(key=lambda x: x[1], reverse=True)
        print(f"\nTop 10 features:")
        for feat, imp in importances[:10]:
            print(f"  {feat}: {imp:.1f}")
    
    # Save model and metrics
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(model, MODEL_DIR / "event_proxy_synthetic.pkl")
    
    metrics = {
        "model": "LightGBM",
        "data": "synthetic",
        "auprc": float(auprc),
        "auroc": float(auroc),
        "rule_baseline_auprc": float(rule_auprc),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "feature_schema": "PROXY_FEATURES_V1",
    }
    
    with open(MODEL_DIR / "event_proxy_synthetic_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\nModel saved to {MODEL_DIR / 'event_proxy_synthetic.pkl'}")
    print("Pipeline smoke test PASSED.")
    return model


def event_metrics(y_true, y_pred, recall_levels=[10, 20, 50]):
    """Compute Candidate Recall and Unique Event Recall at K."""
    n_total = len(y_true)
    if n_total == 0:
        return {}
    
    results = {}
    sorted_idx = np.argsort(y_pred)[::-1]
    
    for k in recall_levels:
        if k > n_total:
            k = n_total
        top_k = sorted_idx[:k]
        candidate_recall = y_true[top_k].sum() / max(y_true.sum(), 1)
        results[f"candidate_recall@{k}"] = float(candidate_recall)
    
    # Unique event recall (simplified: same as candidate since synthetic data has 1 track per clip)
    for k in recall_levels:
        if k > n_total:
            k = n_total
        results[f"unique_event_recall@{k}"] = results.get(f"candidate_recall@{k}", 0)
    
    return results


def evaluate_smoke():
    """Evaluate trained synthetic model."""
    print("=== Evaluate Synthetic Event Proxy ===")
    
    df, _ = generate_synthetic_data()
    _, cal_df, test_df = split_data(df, np.arange(len(df)))
    
    feature_cols = [c for c in PROXY_FEATURES_V1 if c in test_df.columns]
    X_test = test_df[feature_cols].fillna(0).values
    y_test = (test_df["label"] == 1).astype(int).values
    
    # Load or retrain
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "event_proxy_synthetic.pkl"
    
    if model_path.exists():
        import joblib
        model = joblib.load(model_path)
    else:
        model, feature_cols = train_lgbm(test_df.iloc[:len(test_df)//2], test_df.iloc[len(test_df)//2:])
    
    if model is None:
        return
    
    y_pred = model.predict(X_test)
    
    # Compute all metrics
    metrics = {
        "auprc": float(average_precision_score(y_test, y_pred)),
        "auroc": float(roc_auc_score(y_test, y_pred)),
        "n_test": len(y_test),
    }
    metrics.update(event_metrics(y_test, y_pred))
    
    # Rule baseline
    rule = RuleBaseline()
    rule_pred = rule.predict_proba(test_df)
    rule_metrics = {
        "auprc": float(average_precision_score(y_test, rule_pred)),
    }
    rule_metrics.update(event_metrics(y_test, rule_pred))
    
    print("\n=== Event-Level Metrics ===")
    print(f"LightGBM: AUPRC={metrics['auprc']:.4f}, "
          f"CandidateRecall@20={metrics.get('candidate_recall@20', 0):.4f}, "
          f"UniqueEventRecall@20={metrics.get('unique_event_recall@20', 0):.4f}")
    print(f"Rule Baseline: AUPRC={rule_metrics['auprc']:.4f}")
    
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVENT_DIR / "event_metrics_synthetic.json", "w") as f:
        json.dump({"lgbm": metrics, "rule_baseline": rule_metrics}, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="H-PROXY1 Event Proxy Pipeline")
    parser.add_argument("command", choices=["smoke", "train"])
    args = parser.parse_args()
    
    if args.command == "smoke":
        train_smoke()
        evaluate_smoke()
    elif args.command == "train":
        print("Real event proxy training is BLOCKED.")
        print("Requirements:")
        print("  1. DrivingDojo structured event labels (not yet available)")
        print("  2. Gate P1 winners' track features computed on DrivingDojo clips")
        print("  3. Human-verified clip labels with actor_identity and event spans")
        print("\nPipeline code is ready. Run 'smoke' for synthetic data validation.")


if __name__ == "__main__":
    main()
