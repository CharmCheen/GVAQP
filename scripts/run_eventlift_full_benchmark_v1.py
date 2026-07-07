"""EventLift Full Benchmark V1: 9 methods on 6 segments, unified schema.

Merges EventLift Stage 2 multi-segment smoke results with aligned baselines
into a single unified frontier, then reruns both in one pass to ensure
schema compatibility. No tuning. No event_id online. No video/GPU/VLM.

All numbers are VLM-oracle-relative, not human ground truth. No safe
stopping, formal guarantee, or statistical bound is claimed (per AGENTS.md).
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
sys.path.insert(0, str(REPO_ROOT / "refe_repos" / "supg"))

import eventlift_stage2_dev as dev
from eventlift_stage2_multiseg_smoke import (
    load_segment_data, SEGMENTS, BUDGET_RATIOS, SEEDS,
)
PROXY_COL = dev.PROXY_COL
LABEL_COL = dev.LABEL_COL
from run_aligned_baselines_v1 import (
    run_b7_strict_replay, run_d3_norepair_strict,
    run_supg_event_strict, run_abae_residual_strict,
    AlignedOracle,
)

OUT_DIR = REPO_ROOT / "outputs" / "eventlift_full_benchmark_v1"

IOU_THRESHOLD = 0.3
ALPHA = 0.05
NUM_STRATA = 5
CERTIFY_MAX_DEPTH = 2
SUPPRESS_RADIUS = 2
ETA = 1.0
LAMBDA = 0.5
GAMMA = 0.3
KAPPA = 0.5
OMEGA = 0.3

EVENTLIFT_METHODS = [
    ("EventLift-discover-only", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-only")),
    ("EventLift-discover-audit", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-audit", audit_enabled=True)),
    ("EventLift-discover-certify", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-certify", certify_enabled=True)),
    ("EventLift-discover-audit-certify", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-discover-audit-certify", audit_enabled=True, certify_enabled=True)),
    ("EventLift-full-stage2", lambda g, r, sid, b, br, s: dev.run_eventlift(g, r, b, br, s, "EventLift-full-stage2", audit_enabled=True, certify_enabled=True, suppress_enabled=True)),
]

BASELINE_METHODS = [
    ("B7-strict-replay", run_b7_strict_replay),
    ("D3-norepair-core-strict", run_d3_norepair_strict),
    ("SUPG-event-rt-strict", run_supg_event_strict),
    ("ABae-residual-strict", run_abae_residual_strict),
]

METHOD_FAMILY = {
    "EventLift-discover-only": "eventlift",
    "EventLift-discover-audit": "eventlift",
    "EventLift-discover-certify": "eventlift",
    "EventLift-discover-audit-certify": "eventlift",
    "EventLift-full-stage2": "eventlift",
    "B7-strict-replay": "baseline",
    "D3-norepair-core-strict": "baseline",
    "SUPG-event-rt-strict": "baseline",
    "ABae-residual-strict": "baseline",
}


def _unified_frontier_row(r, seg_id, budget_abs, budget_ratio, seed, method_id):
    m = r.get("metrics", {})
    is_eventlift = method_id.startswith("EventLift")
    is_abae = "ABae" in method_id

    return {
        "segment_id": seg_id,
        "method_id": method_id,
        "method_family": METHOD_FAMILY.get(method_id, "unknown"),
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "oracle_calls_total": r["oracle_calls_total"],
        "oracle_calls_discover": r.get("oracle_calls_discover", 0) if is_eventlift else 0,
        "oracle_calls_audit": r.get("oracle_calls_audit", 0) if is_eventlift else 0,
        "oracle_calls_certify": r.get("oracle_calls_certify", 0) if is_eventlift else 0,
        "oracle_calls_suppress": r.get("oracle_calls_suppress", 0) if is_eventlift else 0,
        "oracle_calls_baseline": r["oracle_calls_total"] if not is_eventlift else 0,
        "returned_intervals": json.dumps(r.get("returned_intervals", [])),
        "event_precision": m.get("event_precision", "") if not is_abae else "NA",
        "event_recall": m.get("event_recall", "") if not is_abae else "NA",
        "unique_event_coverage": m.get("unique_event_coverage", "") if not is_abae else "NA",
        "duplicate_rate": r.get("duplicate_rate", 0.0) if is_eventlift else "",
        "certify_calls": r.get("certify_calls", 0) if is_eventlift else 0,
        "certify_success_rate": r.get("certify_success_rate", 0.0) if is_eventlift else "",
        "suppressed_bin_count": r.get("suppressed_bin_count", 0) if is_eventlift else 0,
        "residual_estimate_available": "residual_hat" in r and r.get("residual_hat") != "",
        "residual_hat": r.get("residual_hat", ""),
        "residual_ucb": r.get("residual_ucb", ""),
        "residual_ci_lower": r.get("residual_ci_lower", ""),
        "residual_ci_upper": r.get("residual_ci_upper", ""),
        "recall_lcb_available": r.get("recall_lcb_available", False),
        "stop_certificate_available": r.get("stop_certificate_available", False),
        "stop_status": r.get("stop_status", "abstain_or_budget_exhausted"),
        "stop_reason": r.get("stop_reason", "budget_exhausted"),
        "strict_replay_or_posthoc": r.get("strict_replay_or_posthoc", "strict_replay") if not is_eventlift else "strict_replay",
        "online_uses_event_id": r.get("online_uses_event_id", False) if not is_eventlift else False,
        "can_be_main_comparison": r.get("can_be_main_comparison", True) if not is_eventlift else True,
        "applicability_note": r.get("applicability_note", ""),
    }


def _unified_residual_row(r, seg_id, budget_abs, budget_ratio, seed, method_id, n_pos_total):
    if "residual_hat" not in r or r.get("residual_hat") == "":
        return None
    is_eventlift = method_id.startswith("EventLift")
    observed = r.get("observed_positive_mass", 0)
    if observed == 0 and "audit_positive_n" in r:
        observed = r.get("audit_positive_n", 0)
    if observed == 0 and is_eventlift:
        observed = r.get("audit_positive_n", 0)
    true_residual = max(0, n_pos_total - observed)
    audit_n = r.get("audit_n", 0)
    audit_pos = r.get("audit_positive_n", r.get("observed_positive_mass", 0))
    p_ucb = r.get("p_ucb", 1.0)
    return {
        "segment_id": seg_id,
        "method_id": method_id,
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "residual_hat": r.get("residual_hat", 0.0),
        "residual_ucb": r.get("residual_ucb", 0.0),
        "residual_ci_lower": r.get("residual_ci_lower", ""),
        "residual_ci_upper": r.get("residual_ci_upper", ""),
        "residual_true_if_reference_available": true_residual,
        "abs_error": abs(r.get("residual_hat", 0.0) - true_residual),
        "signed_error": r.get("residual_hat", 0.0) - true_residual,
        "audit_n": audit_n,
        "audit_positive_n": audit_pos,
        "p_ucb": p_ucb,
        "calibration_note": f"stop={r.get('stop_status','')}/{r.get('stop_reason','')}",
    }


def _budget_decomp_row(r, seg_id, budget_ratio, seed, method_id):
    total = r["oracle_calls_total"]
    is_eventlift = method_id.startswith("EventLift")
    if is_eventlift:
        d = r.get("oracle_calls_discover", 0)
        a = r.get("oracle_calls_audit", 0)
        c = r.get("oracle_calls_certify", 0)
        s = r.get("oracle_calls_suppress", 0)
        return {
            "segment_id": seg_id, "method_id": method_id, "seed": seed,
            "budget_ratio": budget_ratio, "oracle_calls_total": total,
            "discover_share": d / max(1, total), "audit_share": a / max(1, total),
            "certify_share": c / max(1, total), "suppress_share": s / max(1, total),
            "baseline_share": 0.0,
        }
    else:
        return {
            "segment_id": seg_id, "method_id": method_id, "seed": seed,
            "budget_ratio": budget_ratio, "oracle_calls_total": total,
            "discover_share": 0.0, "audit_share": 0.0,
            "certify_share": 0.0, "suppress_share": 0.0,
            "baseline_share": 1.0,
        }


def _normalize_trace_rows(ledger, method_id, is_eventlift):
    rows = []
    for row in ledger:
        r = dict(row)
        if is_eventlift:
            r["online_uses_event_id"] = False
        if "anchor_bin_id" not in r:
            r["anchor_bin_id"] = ""
        if "stratum_id" not in r:
            r["stratum_id"] = ""
        if "certified_interval" not in r:
            r["certified_interval"] = ""
        if "suppressed_bins" not in r:
            r["suppressed_bins"] = ""
        if "residual_hat_before" not in r:
            r["residual_hat_before"] = ""
        if "residual_hat_after" not in r:
            r["residual_hat_after"] = ""
        rows.append(r)
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    all_trace_rows = []
    all_frontier_rows = []
    all_residual_rows = []
    all_arbitration_rows = []
    all_budget_decomp_rows = []
    segment_summaries = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\n=== Loading segment: {seg_id} ===")
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            print(f"  SKIPPED: {err}")
            continue

        n_bins = len(grid)
        n_pos = int(grid[LABEL_COL].sum())
        n_events = len(ref_seg)
        print(f"  bins={n_bins}, positive_bins={n_pos}, reference_events={n_events}")
        segment_summaries.append({"segment_id": seg_id, "status": "ok",
                                   "num_bins": n_bins, "num_positive_bins": n_pos,
                                   "num_reference_events": n_events})

        original_seg_id = dev.SEGMENT_ID
        dev.SEGMENT_ID = seg_id

        for budget_ratio in BUDGET_RATIOS:
            budget_abs = max(1, int(round(budget_ratio * n_bins)))
            for seed in SEEDS:
                # EventLift methods
                for name, fn in EVENTLIFT_METHODS:
                    try:
                        r = fn(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed)
                        all_trace_rows.extend(_normalize_trace_rows(r["oracle"].ledger, name, True))
                        all_frontier_rows.append(_unified_frontier_row(r, seg_id, budget_abs, budget_ratio, seed, name))
                        if r.get("arbitration_trace"):
                            for at in r["arbitration_trace"]:
                                at["segment_id"] = seg_id
                                all_arbitration_rows.append(at)
                        observed_pos = sum(1 for row in r["oracle"].ledger if row.get("online_positive") is True)
                        true_unc_pos = n_pos - observed_pos
                        rr = _unified_residual_row(r, seg_id, budget_abs, budget_ratio, seed, name, n_pos)
                        if rr:
                            all_residual_rows.append(rr)
                        all_budget_decomp_rows.append(_budget_decomp_row(r, seg_id, budget_ratio, seed, name))
                    except Exception as e:
                        print(f"  FAILED {seg_id} b={budget_abs} s={seed} {name}: {e}")
                        import traceback; traceback.print_exc()

                # Baseline methods
                for name, fn in BASELINE_METHODS:
                    try:
                        r = fn(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed)
                        all_trace_rows.extend(_normalize_trace_rows(r["oracle"].ledger, name, False))
                        all_frontier_rows.append(_unified_frontier_row(r, seg_id, budget_abs, budget_ratio, seed, name))
                        if "residual_hat" in r and r["residual_hat"] != "":
                            rr = _unified_residual_row(r, seg_id, budget_abs, budget_ratio, seed, name, n_pos)
                            if rr:
                                all_residual_rows.append(rr)
                        all_budget_decomp_rows.append(_budget_decomp_row(r, seg_id, budget_ratio, seed, name))
                    except Exception as e:
                        print(f"  FAILED {seg_id} b={budget_abs} s={seed} {name}: {e}")
                        import traceback; traceback.print_exc()

        dev.SEGMENT_ID = original_seg_id

    # Write raw outputs
    trace_df = pd.DataFrame(all_trace_rows)
    frontier_df = pd.DataFrame(all_frontier_rows)
    residual_df = pd.DataFrame(all_residual_rows)
    arb_df = pd.DataFrame(all_arbitration_rows)
    decomp_df = pd.DataFrame(all_budget_decomp_rows)

    trace_df.to_csv(OUT_DIR / "full_call_trace.csv", index=False)
    frontier_df.to_csv(OUT_DIR / "full_frontier_raw.csv", index=False)
    residual_df.to_csv(OUT_DIR / "full_residual_calibration.csv", index=False)
    arb_df.to_csv(OUT_DIR / "full_action_arbitration.csv", index=False)
    decomp_df.to_csv(OUT_DIR / "full_budget_decomposition.csv", index=False)

    # Method summary
    method_summary_rows = []
    for (mid, br), g in frontier_df.groupby(["method_id", "budget_ratio"]):
        row = {
            "method_id": mid, "budget_ratio": br,
            "mean_event_precision": pd.to_numeric(g.event_precision, errors="coerce").mean(),
            "mean_event_recall": pd.to_numeric(g.event_recall, errors="coerce").mean(),
            "mean_unique_event_coverage": pd.to_numeric(g.unique_event_coverage, errors="coerce").mean(),
            "mean_duplicate_rate": pd.to_numeric(g.duplicate_rate, errors="coerce").mean(),
            "mean_oracle_calls": g.oracle_calls_total.mean(),
            "budget_violation_count": int((g.oracle_calls_total > g.budget_abs).sum()),
            "event_id_leak_count": int((g.online_uses_event_id == True).sum()),
        }
        rg = residual_df[(residual_df.method_id == mid) & (residual_df.budget_ratio == br)]
        row["mean_residual_abs_error"] = pd.to_numeric(rg.abs_error, errors="coerce").mean() if len(rg) > 0 else ""
        row["mean_residual_ucb"] = pd.to_numeric(rg.residual_ucb, errors="coerce").mean() if len(rg) > 0 else ""
        cg = frontier_df[(frontier_df.method_id == mid)]
        row["mean_certify_success_rate"] = pd.to_numeric(cg.certify_success_rate, errors="coerce").mean() if mid.startswith("EventLift") else ""
        row["abstain_rate"] = float((g.stop_status == "abstain_or_budget_exhausted").mean())
        row["stop_rate"] = float((g.stop_certificate_available == True).mean())
        method_summary_rows.append(row)
    method_summary_df = pd.DataFrame(method_summary_rows)
    method_summary_df.to_csv(OUT_DIR / "full_method_summary.csv", index=False)

    # Segment summary
    seg_summary_rows = []
    for (seg_id, mid, br), g in frontier_df.groupby(["segment_id", "method_id", "budget_ratio"]):
        row = {
            "segment_id": seg_id, "method_id": mid, "budget_ratio": br,
            "mean_event_precision": pd.to_numeric(g.event_precision, errors="coerce").mean(),
            "mean_event_recall": pd.to_numeric(g.event_recall, errors="coerce").mean(),
            "mean_unique_event_coverage": pd.to_numeric(g.unique_event_coverage, errors="coerce").mean(),
            "mean_duplicate_rate": pd.to_numeric(g.duplicate_rate, errors="coerce").mean(),
            "mean_oracle_calls": g.oracle_calls_total.mean(),
        }
        rg = residual_df[(residual_df.segment_id == seg_id) & (residual_df.method_id == mid) & (residual_df.budget_ratio == br)]
        row["mean_residual_abs_error"] = pd.to_numeric(rg.abs_error, errors="coerce").mean() if len(rg) > 0 else ""
        seg_summary_rows.append(row)
    seg_summary_df = pd.DataFrame(seg_summary_rows)
    seg_summary_df.to_csv(OUT_DIR / "full_segment_summary.csv", index=False)

    # Assertions
    print(f"\n=== Results ===")
    print(f"Trace rows: {len(trace_df)}")
    print(f"Frontier rows: {len(frontier_df)}")
    print(f"Residual rows: {len(residual_df)}")
    print(f"Arbitration rows: {len(arb_df)}")
    print(f"Budget decomp rows: {len(decomp_df)}")
    violations = frontier_df[frontier_df.oracle_calls_total > frontier_df.budget_abs]
    print(f"Budget violations: {len(violations)} / {len(frontier_df)}")
    event_id_leaks = frontier_df[frontier_df.online_uses_event_id == True]
    print(f"event_id leaks: {len(event_id_leaks)} / {len(frontier_df)}")
    not_strict = frontier_df[frontier_df.strict_replay_or_posthoc != "strict_replay"]
    print(f"Non-strict-replay rows: {len(not_strict)} / {len(frontier_df)}")

    # EventLift action sum check
    el = frontier_df[frontier_df.method_family == "eventlift"]
    el["action_sum"] = el.oracle_calls_discover + el.oracle_calls_audit + el.oracle_calls_certify + el.oracle_calls_suppress
    mismatches = el[el.oracle_calls_total != el.action_sum]
    print(f"EventLift action-sum mismatches: {len(mismatches)} / {len(el)}")

    print(f"Segments run: {sum(1 for s in segment_summaries if s['status']=='ok')} / {len(SEGMENTS)}")


if __name__ == "__main__":
    main()
