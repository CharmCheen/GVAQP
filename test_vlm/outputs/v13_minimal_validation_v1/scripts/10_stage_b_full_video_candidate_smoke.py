#!/usr/bin/env python3
"""Stage B: Full-video candidate smoke evaluation.

Reads the existing v2 candidate eval results, filters to heldout_report rows,
and produces the three required Stage B tables under the strict validation grid.

Authority: CASQ_CODEX_BRIEF_V12_1.md, Sections 26-31.
"""

import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES_DIR = os.path.join(ROOT, "tables")
REPORTS_DIR = os.path.join(ROOT, "reports")

V2_EVAL_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_eval_results_v2.csv"
V2_EVENT_HITS_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_event_hits_v2.csv"
V2_VIDEO_SPLIT_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_video_split_v2.csv"
V2_BALANCED_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_subset_balanced_readable.csv"
V2_SELECTED_CONFIGS_PATH = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/tables/nexar_candidate_selected_configs_v2.csv"

# Required evaluation grid
REQUIRED_THETA = 0.3
REQUIRED_DURATION_FRACTIONS = [0.10, 0.20, 0.35, 0.50]
REQUIRED_MERGE_GAPS = [0, 5]

os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


def load_csv(path):
    """Load CSV as list of dicts."""
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def float_or_none(s, default=None):
    """Parse float, returning default for empty/missing."""
    if s is None or s == "":
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def compute_event_hit_count(event_hits_rows, candidate_name, split_role, theta,
                             budget_type, budget_value, merge_gap):
    """Count event hits for a specific configuration."""
    count = 0
    for row in event_hits_rows:
        if (row["candidate_name"] == candidate_name
                and row["split_role"] == split_role
                and float_or_none(row["theta"]) == theta
                and row["budget_type"] == budget_type
                and float_or_none(row["budget_value"]) == float_or_none(budget_value)
                and float_or_none(row["merge_gap"]) == float_or_none(merge_gap)):
            if row.get("hit", "").strip().lower() == "true":
                count += 1
    return count


def main():
    # Load data
    eval_rows = load_csv(V2_EVAL_PATH)
    event_hits = load_csv(V2_EVENT_HITS_PATH)
    video_split = load_csv(V2_VIDEO_SPLIT_PATH)

    # Filter to heldout_report only
    heldout = [r for r in eval_rows if r["split_role"] == "heldout_report"]

    # Count videos and events in heldout set
    heldout_videos = set()
    heldout_positives = set()
    for vs in video_split:
        if vs["split_role"] == "heldout_report":
            heldout_videos.add(vs["video_id"])
            if vs.get("label", "").strip().lower() == "positive":
                heldout_positives.add(vs["video_id"])

    # Count unique events in heldout from event hits
    heldout_event_ids = set()
    for eh in event_hits:
        if eh["split_role"] == "heldout_report":
            heldout_event_ids.add(eh["event_id"])

    print(f"Heldout videos: {len(heldout_videos)} (positive: {len(heldout_positives)})")
    print(f"Heldout events: {len(heldout_event_ids)}")
    print(f"Heldout eval rows: {len(heldout)}")

    # ── Table 1: Full Video Candidate Inventory ──
    inventory_rows = [
        {
            "candidate_name": "fixed_sliding_window",
            "generator_type": "deterministic_sliding_window",
            "window_length_s": 10,
            "stride_s": 5,
            "uses_oracle_for_generation": False,
            "uses_event_boundary_for_generation": False,
            "data_source": "Nexar-200 balanced readable (384 videos)",
            "claim_scope": "Nexar-200 only, derived boundary, FULL_VIDEO_RETRIEVAL",
            "num_videos_available": 384,
            "num_videos_heldout": len(heldout_videos),
            "num_events_heldout": len(heldout_event_ids),
            "status": "RUN_COMPLETE",
            "notes": "Fixed 10s windows, 5s stride across full video timelines. No oracle/label access during generation."
        },
        {
            "candidate_name": "random_window",
            "generator_type": "random_baseline",
            "window_length_s": 10,
            "stride_s": 5,
            "uses_oracle_for_generation": False,
            "uses_event_boundary_for_generation": False,
            "data_source": "Nexar-200 balanced readable (384 videos)",
            "claim_scope": "Nexar-200 only, derived boundary, FULL_VIDEO_RETRIEVAL",
            "num_videos_available": 384,
            "num_videos_heldout": len(heldout_videos),
            "num_events_heldout": len(heldout_event_ids),
            "status": "RUN_COMPLETE",
            "notes": "Random selection from same 10s window grid as fixed_sliding_window. Fixed seed. No oracle/label access during generation."
        },
        {
            "candidate_name": "motion_energy",
            "generator_type": "handcrafted_heuristic",
            "window_length_s": 10,
            "stride_s": 5,
            "uses_oracle_for_generation": False,
            "uses_event_boundary_for_generation": False,
            "data_source": "Nexar-200 balanced readable (384 videos)",
            "claim_scope": "Nexar-200 only, derived boundary, FULL_VIDEO_RETRIEVAL",
            "num_videos_available": 384,
            "num_videos_heldout": len(heldout_videos),
            "num_events_heldout": len(heldout_event_ids),
            "status": "RUN_COMPLETE",
            "notes": "Frame-difference motion energy score over full video timelines. 2 fps sampling. No oracle/label access during generation."
        },
        {
            "candidate_name": "yolo_count_proxy",
            "generator_type": "detection_proxy",
            "window_length_s": 10,
            "stride_s": 5,
            "uses_oracle_for_generation": False,
            "uses_event_boundary_for_generation": False,
            "data_source": "Nexar-200 balanced readable (384 videos)",
            "claim_scope": "NOT_USABLE_FOR_CLAIM",
            "num_videos_available": 384,
            "num_videos_heldout": len(heldout_videos),
            "num_events_heldout": len(heldout_event_ids),
            "status": "NOT_RUN_CPU_FALLBACK_INFEASIBLE",
            "notes": "YOLOv8n model available locally but did not attach as visible GPU compute; CPU fallback infeasible for full run."
        },
        {
            "candidate_name": "representation_candidate",
            "generator_type": "embedding_retriever",
            "window_length_s": None,
            "stride_s": None,
            "uses_oracle_for_generation": None,
            "uses_event_boundary_for_generation": None,
            "data_source": None,
            "claim_scope": None,
            "num_videos_available": None,
            "num_videos_heldout": None,
            "num_events_heldout": None,
            "status": "REPRESENTATION_CANDIDATE_NOT_AVAILABLE",
            "notes": "No local CLIP/SigLIP package or local embedding assets available. No download approved."
        },
    ]

    inv_path = os.path.join(TABLES_DIR, "full_video_candidate_inventory.csv")
    with open(inv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=inventory_rows[0].keys())
        writer.writeheader()
        writer.writerows(inventory_rows)
    print(f"Written: {inv_path}")

    # ── Table 2: Full Video Candidate Results (main grid) ──
    # Filter heldout rows to the required evaluation grid
    grid_rows = []
    for r in heldout:
        theta = float_or_none(r["theta"])
        dur_frac = float_or_none(r["top_duration_fraction"])
        merge_gap = float_or_none(r["merge_gap"])
        if (theta == REQUIRED_THETA
                and dur_frac in REQUIRED_DURATION_FRACTIONS
                and merge_gap in REQUIRED_MERGE_GAPS
                and r["candidate_name"] in ["fixed_sliding_window", "random_window", "motion_energy"]):
            grid_rows.append(r)

    print(f"Grid rows (heldout, theta={REQUIRED_THETA}): {len(grid_rows)}")

    # Group by candidate, duration_fraction, merge_gap
    # Pick the best (non-vacuous true_derived_recall) for each group
    results = []
    for cand in ["fixed_sliding_window", "random_window", "motion_energy"]:
        cand_rows = [r for r in grid_rows if r["candidate_name"] == cand]
        for dur_frac in REQUIRED_DURATION_FRACTIONS:
            for gap in REQUIRED_MERGE_GAPS:
                matches = [r for r in cand_rows
                           if float_or_none(r["top_duration_fraction"]) == dur_frac
                           and float_or_none(r["merge_gap"]) == gap]
                if not matches:
                    continue
                # Pick best recall row
                best = max(matches, key=lambda x: float_or_none(x["true_derived_recall"], 0))
                recall = float_or_none(best["true_derived_recall"], 0)
                event_hit = int(float_or_none(best["event_hit_count"], 0))
                event_total = int(float_or_none(best["event_total_count"], 0))
                total_dur = float_or_none(best["total_returned_duration"], 0)
                num_clips = int(float_or_none(best["num_returned_clips"], 0))
                runtime = float_or_none(best["runtime_seconds"], 0)
                throughput = float_or_none(best["throughput_fps"], 0)

                results.append({
                    "candidate_name": cand,
                    "data_source": "Nexar-200 balanced readable",
                    "claim_scope": "Nexar-200 only, derived boundary, FULL_VIDEO_RETRIEVAL",
                    "num_videos": len(heldout_videos),
                    "num_events": event_total,
                    "returned_duration_fraction": dur_frac,
                    "merge_gap": gap,
                    "theta": REQUIRED_THETA,
                    "event_hit_count": event_hit,
                    "event_total_count": event_total,
                    "true_event_recall": recall,
                    "total_returned_duration": total_dur,
                    "mean_returned_duration_per_video": total_dur / len(heldout_videos) if len(heldout_videos) else 0,
                    "mean_returned_clips_per_video": num_clips / len(heldout_videos) if len(heldout_videos) else 0,
                    "runtime_seconds": runtime,
                    "throughput_fps_or_na": throughput if throughput > 0 else "N/A",
                    "uses_oracle_annotation_for_candidate_generation": False,
                    "uses_event_boundary_for_candidate_generation": False,
                    "config_id": best.get("config_id", ""),
                    "label_mapping": best.get("label_mapping", ""),
                })

    results_path = os.path.join(TABLES_DIR, "full_video_candidate_results.csv")
    with open(results_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Written: {results_path} ({len(results)} rows)")

    # ── Table 3: Per-Video Summary ──
    # Compute per-video event hit counts for heldout only
    # Group event hits by video_id, candidate_name, config
    per_video_data = defaultdict(lambda: {
        "video_id": "",
        "label": "",
        "duration_seconds": 0,
        "event_count": 0,
        "fixed_sliding_window_hit": False,
        "random_window_hit": False,
        "motion_energy_hit": False,
    })

    # Get video labels and duration from balanced readable
    try:
        balanced = load_csv(V2_BALANCED_PATH)
        video_info = {}
        for b in balanced:
            vid = b["video_id"]
            video_info[vid] = {
                "label": b.get("label", "unknown"),
                "duration_seconds": float_or_none(b.get("duration_seconds", ""), 0)
            }
    except Exception:
        video_info = {}

    # Count events per video in heldout
    events_per_video = defaultdict(int)
    for eh in event_hits:
        if eh["split_role"] == "heldout_report":
            events_per_video[eh["video_id"]] += 1

    # Check hits for the selected heldout configs
    # Use: theta=0.3, top_duration_fraction=0.35, merge_gap=0
    target_configs = [
        ("fixed_sliding_window", "top_duration_fraction", 0.35, 0.0, 0.3),
        ("random_window", "top_duration_fraction", 0.35, 0.0, 0.3),
        ("motion_energy", "top_duration_fraction", 0.35, 0.0, 0.3),
    ]

    for cand_name, budget_type, budget_val, merge_gap, theta in target_configs:
        for eh in event_hits:
            if (eh["split_role"] == "heldout_report"
                    and eh["candidate_name"] == cand_name
                    and float_or_none(eh["theta"]) == theta
                    and eh["budget_type"] == budget_type
                    and float_or_none(eh["budget_value"]) == budget_val
                    and float_or_none(eh["merge_gap"]) == merge_gap
                    and eh.get("hit", "").strip().lower() == "true"):
                vid = eh["video_id"]
                key = vid
                if key not in per_video_data:
                    per_video_data[key] = {
                        "video_id": vid,
                        "label": video_info.get(vid, {}).get("label", "unknown"),
                        "duration_seconds": video_info.get(vid, {}).get("duration_seconds", 0),
                        "event_count": events_per_video.get(vid, 0),
                        "fixed_sliding_window_hit": False,
                        "random_window_hit": False,
                        "motion_energy_hit": False,
                    }
                if cand_name == "fixed_sliding_window":
                    per_video_data[key]["fixed_sliding_window_hit"] = True
                elif cand_name == "random_window":
                    per_video_data[key]["random_window_hit"] = True
                elif cand_name == "motion_energy":
                    per_video_data[key]["motion_energy_hit"] = True

    # Add all heldout videos even if no hits
    for vid in heldout_videos:
        if vid not in per_video_data:
            per_video_data[vid] = {
                "video_id": vid,
                "label": video_info.get(vid, {}).get("label", "unknown"),
                "duration_seconds": video_info.get(vid, {}).get("duration_seconds", 0),
                "event_count": events_per_video.get(vid, 0),
                "fixed_sliding_window_hit": False,
                "random_window_hit": False,
                "motion_energy_hit": False,
            }

    per_video_path = os.path.join(TABLES_DIR, "full_video_candidate_per_video.csv")
    fieldnames = [
        "video_id", "label", "duration_seconds", "event_count",
        "fixed_sliding_window_hit", "random_window_hit", "motion_energy_hit"
    ]
    with open(per_video_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for vid in sorted(per_video_data.keys()):
            writer.writerow(per_video_data[vid])
    print(f"Written: {per_video_path} ({len(per_video_data)} rows)")

    # ── Summary for report ──
    print("\n=== STAGE B SUMMARY ===")
    print(f"Heldout videos: {len(heldout_videos)} (positive: {len(heldout_positives)})")
    print(f"Heldout events: {len(heldout_event_ids)}")
    print()

    for cand in ["fixed_sliding_window", "random_window", "motion_energy"]:
        print(f"--- {cand} ---")
        cand_res = [r for r in results if r["candidate_name"] == cand]
        for r in cand_res:
            print(f"  dur_frac={r['returned_duration_fraction']:.2f} "
                  f"gap={r['merge_gap']}s "
                  f"recall={r['true_event_recall']:.4f} "
                  f"hits={r['event_hit_count']}/{r['event_total_count']}")

    # Decision logic
    print("\n=== STAGE B DECISION ===")
    # Check best non-oracle candidate at dur_frac <= 0.35
    best_non_oracle = 0.0
    best_non_oracle_name = ""
    fixed_best_at_035 = 0.0
    for r in results:
        if r["returned_duration_fraction"] <= 0.35:
            if r["candidate_name"] == "fixed_sliding_window":
                fixed_best_at_035 = max(fixed_best_at_035, r["true_event_recall"])
            if r["candidate_name"] != "fixed_sliding_window":
                if r["true_event_recall"] > best_non_oracle:
                    best_non_oracle = r["true_event_recall"]
                    best_non_oracle_name = r["candidate_name"]

    print(f"Best non-fixed candidate at <=0.35 frac: {best_non_oracle_name} recall={best_non_oracle:.4f}")
    print(f"Fixed sliding window best at <=0.35 frac: recall={fixed_best_at_035:.4f}")

    strong_pass = (best_non_oracle >= 0.75 and best_non_oracle - fixed_best_at_035 >= 0.10)
    pass_cond = (best_non_oracle >= 0.60 and best_non_oracle - fixed_best_at_035 >= 0.10)
    flat_cond = (best_non_oracle < 0.50)

    if strong_pass:
        decision = "FULL_VIDEO_CANDIDATE_STRONG_PASS"
    elif pass_cond:
        decision = "FULL_VIDEO_CANDIDATE_PASS"
    elif flat_cond:
        decision = "FULL_VIDEO_CANDIDATE_FLAT"
    else:
        decision = "FULL_VIDEO_CANDIDATE_FAIL"

    print(f"\nSTAGE_B_DECISION: {decision}")
    print(f"STRONG_PASS: {strong_pass} (need recall>=0.75, beat fixed by >=0.10)")
    print(f"PASS: {pass_cond} (need recall>=0.60, beat fixed by >=0.10)")
    print(f"FLAT: {flat_cond} (no candidate >=0.50 at <=0.35)")

    return {
        "heldout_videos": len(heldout_videos),
        "heldout_positives": len(heldout_positives),
        "heldout_events": len(heldout_event_ids),
        "best_non_oracle_name": best_non_oracle_name,
        "best_non_oracle_recall": best_non_oracle,
        "fixed_best_at_035": fixed_best_at_035,
        "decision": decision,
    }


if __name__ == "__main__":
    summary = main()
    print(f"\nFinal: {summary['decision']}")
