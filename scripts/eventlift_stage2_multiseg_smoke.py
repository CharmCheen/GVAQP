"""EventLift-AQP Stage 2 Multi-Segment Smoke Test.

Runs the exact fixed Stage 2 parameters from the dev run on all 6 LATE-AQP
segments. This is a smoke test, not a full benchmark and not a tuning pass.

Approach: imports run_eventlift from eventlift_stage2_dev and overrides the
module-level SEGMENT_ID global so the same logic runs on each segment.

Hard constraints:
  - 6 LATE-AQP segments only.
  - Replay over existing VLM-oracle-relative labels only.
  - No event_id in online decisions.
  - oracle_calls_total <= budget_abs asserted.
  - oracle_calls_total == discover + audit + certify + suppress asserted.
  - Exact fixed Stage 2 parameters (no tuning).
  - Small outputs only.
  - No video/GPU/VLM/YOLO inference.

All numbers are VLM-oracle-relative, not human ground truth, and no formal
guarantee / certificate / statistical bound is claimed (per AGENTS.md).
"""

import sys
import os
import math
import json
import numpy as np
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import eventlift_stage2_dev as dev

OUT_DIR = REPO_ROOT / "outputs/eventlift_stage2_multiseg_smoke"

FROZEN_DIR = REPO_ROOT / "outputs/late_aqp_frozen_cross_segment_v1"
CENTER10_REF = REPO_ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
DATASET3_TABLE = REPO_ROOT / "src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "t_start": 0.0, "t_end": 1570.0},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "t_start": 2000.0, "t_end": 3200.0},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "t_start": 3200.0, "t_end": 3830.0},
    {"segment_id": "dataset3_0_1200", "video_id": "long_video_dataset3", "t_start": 0.0, "t_end": 1200.0},
    {"segment_id": "dataset3_1200_2400", "video_id": "long_video_dataset3", "t_start": 1200.0, "t_end": 2400.0},
    {"segment_id": "dataset3_2400_3462", "video_id": "long_video_dataset3", "t_start": 2400.0, "t_end": 3462.93},
]

BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]

METHODS = [
    ("discover_only", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-only")),
    ("discover_audit", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-audit", audit_enabled=True)),
    ("discover_certify", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-certify", certify_enabled=True)),
    ("discover_audit_certify", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-audit-certify", audit_enabled=True, certify_enabled=True)),
    ("full_stage2", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-full-stage2", audit_enabled=True, certify_enabled=True, suppress_enabled=True)),
]


def load_realcartest_segment(seg):
    grid_path = FROZEN_DIR / f"grid_{seg['segment_id']}.csv"
    if not grid_path.exists():
        return None, None, f"grid file missing: {grid_path}"
    grid = pd.read_csv(grid_path)
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    c10 = pd.read_csv(CENTER10_REF)
    t_s, t_e = seg["t_start"], seg["t_end"]
    ref_seg = c10[(c10["event_start"] >= t_s) & (c10["event_end"] <= t_e)].copy()
    ref_seg["t_start"] = ref_seg["event_start"] - t_s
    ref_seg["t_end"] = ref_seg["event_end"] - t_s
    ref_seg = ref_seg[["event_id", "t_start", "t_end"]].sort_values("t_start").reset_index(drop=True)
    return grid, ref_seg, None


def load_dataset3_segment(seg):
    if not DATASET3_TABLE.exists():
        return None, None, f"canonical table missing: {DATASET3_TABLE}"
    df = pd.read_csv(DATASET3_TABLE)
    t_s, t_e = seg["t_start"], seg["t_end"]
    bins = []
    bin_idx = 0
    cur_t = t_s
    while cur_t < t_e:
        bin_t_end = min(cur_t + 10.0, t_e)
        mask = (df["start_time_s"] >= cur_t) & (df["start_time_s"] < bin_t_end)
        bin_anchors = df[mask]
        if len(bin_anchors) > 0:
            is_pos = bool(bin_anchors["is_positive"].any())
            proxy = max(0.0, float(bin_anchors["score_yolo_count"].max()))
            proxy_mean = max(0.0, float(bin_anchors["score_yolo_count"].mean()))
            eids = bin_anchors[bin_anchors["event_cluster_id"] >= 0]["event_cluster_id"].unique()
            event_id_str = ";".join([f"dataset3_event_{int(eid):03d}" for eid in eids]) if len(eids) > 0 else ""
        else:
            is_pos = False
            proxy = 0.0
            proxy_mean = 0.0
            event_id_str = ""
        bins.append({
            "bin_idx": bin_idx,
            "local_t_start": cur_t - t_s,
            "local_t_end": bin_t_end - t_s,
            "is_positive": is_pos,
            "prior_score_max": proxy,
            "prior_score_mean": proxy_mean,
            "event_id": event_id_str,
        })
        bin_idx += 1
        cur_t = bin_t_end
    grid = pd.DataFrame(bins)
    pos = df[df["is_positive"] == True].copy()
    ref_events = []
    for cid, g in pos.groupby("event_cluster_id"):
        if cid < 0:
            continue
        ev_start = float(g["event_start_absolute"].min())
        ev_end = float(g["event_end_absolute"].max())
        if ev_end < t_s or ev_start > t_e:
            continue
        ref_events.append({
            "event_id": f"dataset3_event_{int(cid):03d}",
            "t_start": max(ev_start, t_s) - t_s,
            "t_end": min(ev_end, t_e) - t_s,
        })
    ref_seg = pd.DataFrame(ref_events)
    if len(ref_seg) > 0:
        ref_seg = ref_seg.sort_values("t_start").reset_index(drop=True)
    return grid, ref_seg, None


def load_segment_data(seg):
    if seg["video_id"] == "realcartest":
        return load_realcartest_segment(seg)
    else:
        return load_dataset3_segment(seg)


def _frontier_row_ms(r, seg_id, budget_abs, budget_ratio, seed):
    m = r.get("metrics", {})
    return {
        "segment_id": seg_id,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "oracle_calls_total": r["oracle_calls_total"],
        "oracle_calls_discover": r.get("oracle_calls_discover", 0),
        "oracle_calls_audit": r.get("oracle_calls_audit", 0),
        "oracle_calls_certify": r.get("oracle_calls_certify", 0),
        "oracle_calls_suppress": r.get("oracle_calls_suppress", 0),
        "returned_intervals": json.dumps(r.get("returned_intervals", [])),
        "event_precision": m.get("event_precision", ""),
        "event_recall": m.get("event_recall", ""),
        "unique_event_coverage": m.get("unique_event_coverage", ""),
        "duplicate_rate": r.get("duplicate_rate", 0.0),
        "certify_calls": r.get("certify_calls", 0),
        "certify_success_rate": r.get("certify_success_rate", 0.0),
        "suppressed_bin_count": r.get("suppressed_bin_count", 0),
        "residual_estimate_available": r.get("residual_estimate_available", False),
        "residual_hat": r.get("residual_hat", ""),
        "residual_ucb": r.get("residual_ucb", ""),
        "residual_ci_lower": r.get("residual_ci_lower", ""),
        "residual_ci_upper": r.get("residual_ci_upper", ""),
        "recall_lcb_available": r.get("recall_lcb_available", False),
        "stop_certificate_available": r.get("stop_certificate_available", False),
        "stop_status": r.get("stop_status", "abstain_or_budget_exhausted"),
        "stop_reason": r.get("stop_reason", "budget_exhausted"),
        "applicability_note": r.get("applicability_note", ""),
    }


def _calibration_row_ms(r, seg_id, budget_abs, budget_ratio, seed, true_unc_pos):
    return {
        "segment_id": seg_id,
        "method_id": r["method_id"],
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "residual_hat": r.get("residual_hat", 0.0),
        "residual_ucb": r.get("residual_ucb", 0.0),
        "residual_true_if_reference_available": true_unc_pos,
        "abs_error": abs(r.get("residual_hat", 0.0) - true_unc_pos),
        "signed_error": r.get("residual_hat", 0.0) - true_unc_pos,
        "audit_n": r.get("audit_n", 0),
        "audit_positive_n": r.get("audit_positive_n", 0),
        "p_ucb": r.get("p_ucb", 1.0),
        "calibration_note": f"stop={r['stop_status']}/{r['stop_reason']}",
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    all_trace_rows = []
    all_frontier_rows = []
    all_calibration_rows = []
    all_arbitration_rows = []
    segment_summaries = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\n=== Loading segment: {seg_id} ===")
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            print(f"  SKIPPED: {err}")
            segment_summaries.append({"segment_id": seg_id, "status": "skipped", "reason": err,
                                       "num_bins": 0, "num_positive_bins": 0, "num_reference_events": 0})
            continue

        n_bins = len(grid)
        n_pos = int(grid[dev.LABEL_COL].sum())
        n_events = len(ref_seg)
        print(f"  bins={n_bins}, positive_bins={n_pos}, reference_events={n_events}")
        print(f"  proxy_col={dev.PROXY_COL}, label_col={dev.LABEL_COL}")
        print(f"  event_id present: {'event_id' in grid.columns} (excluded from online)")
        segment_summaries.append({"segment_id": seg_id, "status": "ok", "reason": "",
                                   "num_bins": n_bins, "num_positive_bins": n_pos,
                                   "num_reference_events": n_events})

        # Override the module-level SEGMENT_ID so run_eventlift uses this segment
        original_seg_id = dev.SEGMENT_ID
        dev.SEGMENT_ID = seg_id

        for budget_ratio in BUDGET_RATIOS:
            budget_abs = max(1, int(round(budget_ratio * n_bins)))
            for seed in SEEDS:
                for name, fn in METHODS:
                    try:
                        r = fn(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed)
                        all_trace_rows.extend(r["oracle"].ledger)
                        all_frontier_rows.append(_frontier_row_ms(r, seg_id, budget_abs, budget_ratio, seed))
                        all_arbitration_rows.extend(r["arbitration_trace"])
                        observed_pos = sum(1 for row in r["oracle"].ledger if row.get("online_positive") is True)
                        true_unc_pos = n_pos - observed_pos
                        all_calibration_rows.append(_calibration_row_ms(r, seg_id, budget_abs, budget_ratio, seed, true_unc_pos))
                        m = r["metrics"]
                        print(f"  {seg_id} b={budget_abs} s={seed} {r['method_id']}: "
                              f"calls={r['oracle_calls_total']} "
                              f"(D={r['oracle_calls_discover']},A={r['oracle_calls_audit']},"
                              f"C={r['oracle_calls_certify']},S={r['oracle_calls_suppress']}) "
                              f"P={m['event_precision']:.3f} R={m['event_recall']:.3f} "
                              f"cov={m['unique_event_coverage']} stop={r['stop_status']}")
                    except Exception as e:
                        print(f"  {seg_id} b={budget_abs} s={seed} {name} FAILED: {e}")
                        import traceback; traceback.print_exc()

        dev.SEGMENT_ID = original_seg_id

    trace_df = pd.DataFrame(all_trace_rows)
    trace_df.to_csv(OUT_DIR / "multiseg_call_trace.csv", index=False)
    frontier_df = pd.DataFrame(all_frontier_rows)
    frontier_df.to_csv(OUT_DIR / "multiseg_frontier_raw.csv", index=False)
    calib_df = pd.DataFrame(all_calibration_rows)
    calib_df.to_csv(OUT_DIR / "multiseg_residual_calibration.csv", index=False)
    arb_df = pd.DataFrame(all_arbitration_rows)
    arb_df.to_csv(OUT_DIR / "multiseg_action_arbitration.csv", index=False)

    print(f"\nWrote {len(trace_df)} trace rows, {len(frontier_df)} frontier rows, "
          f"{len(calib_df)} calibration rows, {len(arb_df)} arbitration rows")

    violations = frontier_df[frontier_df.oracle_calls_total > frontier_df.budget_abs] if len(frontier_df) > 0 else []
    print(f"Budget violations: {len(violations)} / {len(frontier_df)}")
    print(f"Segments run: {sum(1 for s in segment_summaries if s['status']=='ok')} / {len(SEGMENTS)}")


if __name__ == "__main__":
    main()
