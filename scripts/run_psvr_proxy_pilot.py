#!/usr/bin/env python3
"""
PSVR Proxy Integration — Physical Pilot.

Integrates frozen Y8-R proxy (YOLOv8n + rule head) into PSVR runtime.
Computes proxy scores for all 347 oracle units, then simulates a
neutral Uniform-Temporal-Interleave scanner with A0 Fixed-Periodic VERIFY.

This is a "physical-light" pilot: proxy inference is real (YOLOv8n on GPU),
oracle labels are read from frozen reference (post-ranking), and PSVR metrics
are computed from the actual proxy ranking order.

Usage:
  python scripts/run_psvr_proxy_pilot.py scan     # Compute proxy scores for all 347 units
  python scripts/run_psvr_proxy_pilot.py pilot    # Run neutral-scheduler PSVR simulation
  python scripts/run_psvr_proxy_pilot.py gate     # Proxy-value gate comparison
"""

import sys, os, json, time, hashlib, argparse, warnings
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import cv2

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/psvr_proxy_finalization_v0"
ORACLE_REF_DIR = PROJECT_ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
YOLOV8N_PATH = PROJECT_ROOT / "models/yolo/yolov8n.pt"
PREV_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"

UNIT_DURATION = 10.0
VIDEO_FPS = 30.0
UNIT_FRAMES = 300


def compute_proxy_scores_all_units():
    """Compute Y8-R proxy score for all 347 units using real YOLOv8n detections."""
    print("=== Scanning: Y8-R Proxy Scores for All 347 Units ===")
    
    # Use existing detections
    det_path = PREV_DIR / "raw/detections/B0_yolov8n_dets.parquet"
    if not det_path.exists():
        print("ERROR: B0 detections not found")
        return None

    dets = pd.read_parquet(det_path)
    print(f"Loaded {len(dets)} detections from {det_path}")

    # Oracle reference for unit definitions
    oracle_path = ORACLE_REF_DIR / "frozen_inputs/oracle_observations.csv"
    oracle_df = pd.read_csv(oracle_path)
    n_units = len(oracle_df)
    n_pos = (oracle_df["parsed_label"] == "positive").sum()

    # Compute per-unit proxy scores
    proxy_rows = []
    total_gpu_sec = 0.0

    for unit_id in range(n_units):
        start_frame = unit_id * UNIT_FRAMES
        end_frame = start_frame + UNIT_FRAMES

        unit_dets = dets[(dets["frame_index"] >= start_frame) & (dets["frame_index"] < end_frame)]

        det_count = len(unit_dets)
        max_conf = float(unit_dets["confidence"].max()) if len(unit_dets) > 0 else 0.0

        # Y8-R rule: normalized count + max confidence
        score = 0.5 * min(det_count, 20) / 20.0 + 0.5 * max_conf

        proxy_rows.append({
            "unit_id": unit_id,
            "proxy_score": float(score),
            "det_count": det_count,
            "max_conf": max_conf,
            "start_time": unit_id * UNIT_DURATION,
            "end_time": (unit_id + 1) * UNIT_DURATION,
        })

        # Estimate GPU cost per unit (from physical cost profile)
        total_gpu_sec += 1.0 / 128.5  # ~7.8ms per frame, but per-unit we just use avg

    df_proxy = pd.DataFrame(proxy_rows)
    df_proxy.to_csv(OUTPUT_DIR / "psvr_physical/proxy_scores_all_347.csv", index=False)
    
    print(f"Computed scores for {n_units} units")
    print(f"  Score range: [{df_proxy['proxy_score'].min():.4f}, {df_proxy['proxy_score'].max():.4f}]")
    print(f"  Score mean: {df_proxy['proxy_score'].mean():.4f}")
    print(f"  Oracle positives: {n_pos} units")

    # Save proxy spec
    proxy_spec = {
        "proxy_id": "Y8-R",
        "family": "YOLOV8",
        "detector": "YOLOv8n",
        "weights_sha256": "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
        "head": "RULE_BASELINE",
        "score_formula": "0.5 * min(det_count,20)/20 + 0.5 * max_conf",
        "n_units": n_units,
        "score_range": [float(df_proxy["proxy_score"].min()), float(df_proxy["proxy_score"].max())],
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(OUTPUT_DIR / "psvr_physical/PROXY_SCAN_SPEC.json", "w") as f:
        json.dump(proxy_spec, f, indent=2)

    return df_proxy


def simulate_psvr_run(proxy_df, oracle_df, horizon, verify_every_n=3):
    """Simulate PSVR with neutral scheduler: Uniform Temporal Interleave + Fixed-Periodic VERIFY.

    horizon: number of units to process (proxy for T_short/T_mid/T_long)
    verify_every_n: scan N units before each VERIFY call (A0 Fixed-Periodic)
    """
    # Merge proxy scores with oracle labels
    df = proxy_df.merge(oracle_df[["unit_id", "parsed_label", "confidence", "latency_seconds"]],
                        on="unit_id", how="left")
    df["is_positive"] = (df["parsed_label"] == "positive").astype(int)
    
    n_total = len(df)
    horizon = min(horizon, n_total)
    
    # Uniform temporal interleave: scan units in order of unit_id
    # (units are already temporal — unit 0 = t=0-10s, unit 1 = t=10-20s, etc.)
    # Interleave: 0, horizon//2, 1, horizon//2+1, ...
    scan_order = []
    half = horizon // 2
    for i in range(half):
        scan_order.append(i)
        if i + half < horizon:
            scan_order.append(i + half)
    # Add remaining
    for i in range(horizon - len(scan_order)):
        scan_order.append(half + i if half + i < horizon else i)
    
    # A0 Fixed-Periodic: VERIFY every N scanned units
    verified = []
    proxy_scores_exposed = {}  # unit_id -> (score, exposure_time)
    scan_count = 0
    total_latency = 0.0  # cumulative oracle latency
    
    for scan_idx, unit_id in enumerate(scan_order):
        # "Scan" this unit — its proxy score becomes available
        score = float(df.iloc[unit_id]["proxy_score"])
        proxy_scores_exposed[unit_id] = score
        scan_count += 1
        
        # Fixed-periodic VERIFY
        if scan_count % verify_every_n == 0:
            # Select highest-score scanned but not-yet-verified unit
            eligible = [(uid, s) for uid, s in proxy_scores_exposed.items()
                       if uid not in {v["unit_id"] for v in verified}]
            if not eligible:
                continue
            
            # Rank by proxy score (descending)
            eligible.sort(key=lambda x: -x[1])
            selected = eligible[0][0]
            
            # VERIFY: read oracle label (simulating VLM call)
            oracle_row = df.iloc[selected]
            is_pos = oracle_row["is_positive"]
            latency = float(oracle_row.get("latency_seconds", 20.0))
            
            verified.append({
                "unit_id": selected,
                "is_positive": int(is_pos),
                "scan_count_at_verify": scan_count,
                "cumulative_latency": total_latency + latency,
                "proxy_score": proxy_scores_exposed[selected],
            })
            total_latency += latency
    
    return verified, scan_order


def compute_psvr_metrics(verified_units, oracle_df, horizon):
    """Compute PSVR anytime metrics from verified unit trace."""
    n_events_total = 26  # from event_reference.csv
    n_pos_units = int((oracle_df["parsed_label"] == "positive").sum())
    
    if not verified_units:
        return {"unique_events": 0, "anytime_auc_f1": 0.0, "ttfc": None}
    
    # Find unique events recovered
    events_path = ORACLE_REF_DIR / "frozen_inputs/event_reference.csv"
    events_df = pd.read_csv(events_path)
    
    # Map positive units to events
    oracle_df["unit_id"] = oracle_df["unit_id"].astype(int)
    pos_units = oracle_df[oracle_df["parsed_label"] == "positive"]
    
    recovered_events = set()
    for vu in verified_units:
        if vu["is_positive"]:
            unit_id = vu["unit_id"]
            # Find which event this unit belongs to
            for _, evt in events_df.iterrows():
                event_start = evt["start_time"]
                event_end = evt["end_time"]
                unit_start = unit_id * UNIT_DURATION
                unit_end = unit_start + UNIT_DURATION
                # Overlap check
                if unit_start < event_end and unit_end > event_start:
                    recovered_events.add(evt["reference_event_id"])
    
    n_unique_events = len(recovered_events)
    
    # Time to first confirmed event
    ttfc = None
    for vu in verified_units:
        if vu["is_positive"]:
            ttfc = vu["cumulative_latency"]
            break
    
    # Anytime AUC: cumulative unique events / total events, integrated over verify steps
    cum_events = []
    seen = set()
    for vu in verified_units:
        if vu["is_positive"]:
            unit_id = vu["unit_id"]
            for _, evt in events_df.iterrows():
                unit_start = unit_id * UNIT_DURATION
                unit_end = unit_start + UNIT_DURATION
                if unit_start < evt["end_time"] and unit_end > evt["start_time"]:
                    seen.add(evt["reference_event_id"])
        cum_events.append(len(seen))
    
    if cum_events:
        anytime_auc = np.trapz(cum_events) / (n_events_total * len(cum_events)) if n_events_total > 0 else 0
    else:
        anytime_auc = 0.0
    
    # Precision and F1 at final point
    n_verified = len(verified_units)
    n_tp = sum(1 for vu in verified_units if vu["is_positive"])
    precision = n_tp / max(n_verified, 1)
    recall = n_tp / max(n_pos_units, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-6)
    
    return {
        "unique_confirmed_events": n_unique_events,
        "anytime_auc_events": float(anytime_auc),
        "f1_at_endpoint": float(f1),
        "precision": float(precision),
        "recall": float(recall),
        "ttfc_seconds": ttfc,
        "verified_units": n_verified,
        "tp_units": n_tp,
        "recovered_event_ids": sorted(recovered_events),
    }


def run_psvr_pilot():
    """I-E: Neutral-scheduler PSVR physical pilot."""
    print("=" * 60)
    print("Phase I-E: Neutral PSVR Physical Pilot")
    print("=" * 60)

    # Load or compute proxy scores
    proxy_path = OUTPUT_DIR / "psvr_physical/proxy_scores_all_347.csv"
    if proxy_path.exists():
        proxy_df = pd.read_csv(proxy_path)
    else:
        proxy_df = compute_proxy_scores_all_units()
    
    if proxy_df is None:
        return

    oracle_path = ORACLE_REF_DIR / "frozen_inputs/oracle_observations.csv"
    oracle_df = pd.read_csv(oracle_path)

    # Deadlines from PSVR profile
    horizons = {"T_short": 10, "T_mid": 40, "T_long": 100}
    
    # Compare: Q0 = old simple proxy, Q1 = Y8-R proxy
    # Q0 uses simple det_count only (no max_conf weight)
    proxy_df["q0_score"] = np.clip(proxy_df["det_count"], 0, 20) / 20.0
    
    results = []
    for horizon_name, horizon in horizons.items():
        print(f"\n--- {horizon_name} (horizon={horizon} units) ---")
        
        # Q1: Y8-R proxy
        _, scan_order_q1 = simulate_psvr_run(proxy_df, oracle_df, horizon, verify_every_n=3)
        verified_q1, _ = simulate_psvr_run(proxy_df, oracle_df, horizon, verify_every_n=3)
        
        # Re-run with explicit proxy_score column
        proxy_for_q1 = proxy_df.copy()
        proxy_for_q1["proxy_score"] = proxy_df["proxy_score"]  # Y8-R
        verified_q1, scan_order = simulate_psvr_run(proxy_for_q1, oracle_df, horizon, verify_every_n=3)
        metrics_q1 = compute_psvr_metrics(verified_q1, oracle_df, horizon)
        
        # Q0: simple count proxy
        proxy_for_q0 = proxy_df.copy()
        proxy_for_q0["proxy_score"] = proxy_df["q0_score"]  # simple count
        verified_q0, _ = simulate_psvr_run(proxy_for_q0, oracle_df, horizon, verify_every_n=3)
        metrics_q0 = compute_psvr_metrics(verified_q0, oracle_df, horizon)
        
        print(f"  Q0 (simple count): events={metrics_q0['unique_confirmed_events']}, "
              f"F1={metrics_q0['f1_at_endpoint']:.4f}, TTFC={metrics_q0.get('ttfc_seconds', 'N/A')}s")
        print(f"  Q1 (Y8-R rule):    events={metrics_q1['unique_confirmed_events']}, "
              f"F1={metrics_q1['f1_at_endpoint']:.4f}, TTFC={metrics_q1.get('ttfc_seconds', 'N/A')}s")
        
        results.append({
            "horizon": horizon_name,
            "horizon_units": horizon,
            "q0_unique_events": metrics_q0["unique_confirmed_events"],
            "q1_unique_events": metrics_q1["unique_confirmed_events"],
            "q0_f1": metrics_q0["f1_at_endpoint"],
            "q1_f1": metrics_q1["f1_at_endpoint"],
            "q0_ttfc": metrics_q0.get("ttfc_seconds", None),
            "q1_ttfc": metrics_q1.get("ttfc_seconds", None),
            "q0_verified": metrics_q0["verified_units"],
            "q1_verified": metrics_q1["verified_units"],
        })

    df_results = pd.DataFrame(results)
    df_results.to_csv(OUTPUT_DIR / "psvr_physical/PSVR_METHOD_METRICS.csv", index=False)

    # Gate decision
    print("\n=== Proxy Value Gate ===")
    q1_best = df_results[df_results["horizon"] == "T_long"]
    if len(q1_best) > 0:
        r = q1_best.iloc[0]
        if r["q1_unique_events"] > r["q0_unique_events"]:
            print(f"PASS: Q1 recovers {r['q1_unique_events']} events vs Q0's {r['q0_unique_events']} at T_long")
            print("PROXY_VALUE_GATE = PASS")
        elif r["q1_unique_events"] == r["q0_unique_events"] and r["q1_ttfc"] and r["q0_ttfc"]:
            if r["q1_ttfc"] < r["q0_ttfc"] * 0.8:
                print(f"PASS: Q1 TTFC ({r['q1_ttfc']:.1f}s) < 80% of Q0 ({r['q0_ttfc']:.1f}s)")
                print("PROXY_VALUE_GATE = PASS")
            else:
                print(f"WEAK: Same events, TTFC not significantly better")
                print("PROXY_VALUE_GATE = WEAK")
        else:
            print(f"NO_GAIN: Q1 and Q0 recover same events")
            print("PROXY_VALUE_GATE = NO_GAIN")
    
    return df_results


def run_proxy_value_gate():
    """Compare Q0 (old simple count proxy) vs Q1 (Y8-R)."""
    return run_psvr_pilot()


def main():
    parser = argparse.ArgumentParser(description="PSVR Proxy Integration Pilot")
    parser.add_argument("command", choices=["scan", "pilot", "gate"], default="pilot", nargs="?")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "psvr_physical").mkdir(parents=True, exist_ok=True)

    if args.command == "scan":
        compute_proxy_scores_all_units()
    elif args.command in ("pilot", "gate"):
        run_psvr_pilot()


if __name__ == "__main__":
    main()
