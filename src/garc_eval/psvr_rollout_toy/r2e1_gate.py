"""Literal R2 Gate reconstruction from independent verifier metrics only."""
from __future__ import annotations

from statistics import median

M1="M1_EXACT_VISIBLE_HISTORY_ROLLOUT"
SIMPLE=("B0_SCAN_THEN_CONFIRM","B2_FIXED_PERIODIC_K1","B2_FIXED_PERIODIC_K2","B2_FIXED_PERIODIC_K4","B2_FIXED_PERIODIC_K8","B3_CAPACITY_MATCHING","B4_RATIO_PSVR")

def _mean(values: list[float]) -> float: return sum(values)/len(values)

def evaluate_frozen_gate(metrics: list[dict]) -> dict:
    """Same comparator selection and neighborhood rule as frozen R2 runner."""
    by_episode={}
    for row in metrics: by_episode.setdefault(row["episode_public_id"],{})[row["method_id"]]=row
    required={M1,"B1_SHIELDED_PI0","B4_RATIO_PSVR",*SIMPLE}
    incomplete=[episode for episode,methods in by_episode.items() if set(methods) != required]
    if not by_episode or incomplete:
        return {"integrity":"FAIL","reason":"incomplete frozen method pairing","incomplete_episodes":sorted(incomplete)}
    rows=[]
    for episode, methods in sorted(by_episode.items()):
        reference=methods[M1]
        rows.append({"episode_public_id":episode,"process":reference["process"],"cost_regime":reference["cost_regime"],"density_bin":reference["density_bin"],"cost_variance_bin":reference["cost_variance_bin"],"metrics":methods})
    means={method:_mean([row["metrics"][method]["primary_utility"] for row in rows]) for method in SIMPLE}
    best_simple=max(SIMPLE,key=lambda method:means[method])
    comparators=("B1_SHIELDED_PI0","B4_RATIO_PSVR",best_simple)
    paired={method:[row["metrics"][M1]["primary_utility"]-row["metrics"][method]["primary_utility"] for row in rows] for method in required-{M1}}
    regime={}
    for process in sorted({row["process"] for row in rows}):
        for cost in sorted({row["cost_regime"] for row in rows}):
            subset=[row for row in rows if row["process"]==process and row["cost_regime"]==cost]
            if subset: regime[f"{process}|{cost}"]={method:_mean([row["metrics"][M1]["primary_utility"]-row["metrics"][method]["primary_utility"] for row in subset]) for method in comparators}
    families={"SPARSE":lambda row:row["process"]=="UNIFORM_SPARSE","BURSTY":lambda row:row["process"]=="BURSTY_CLUSTERED","HETEROGENEOUS_COST":lambda row:row["cost_variance_bin"]>=2}
    neighborhoods={}; positive_families=0
    for family,predicate in families.items():
        bins=[]
        for density in range(8):
            subset=[row for row in rows if predicate(row) and row["density_bin"]==density]
            entry={"n":len(subset)}
            for method in ("B1_SHIELDED_PI0",best_simple):
                deltas=[row["metrics"][M1]["primary_utility"]-row["metrics"][method]["primary_utility"] for row in subset]
                threshold=1e-8*max(1.0,_mean([row["metrics"][M1]["primary_utility"] for row in subset])) if subset else float("inf")
                entry[method]={"mean":_mean(deltas) if deltas else None,"median":median(deltas) if deltas else None,"threshold":threshold,"positive":bool(len(subset)>=12 and _mean(deltas)>threshold and median(deltas)>=0)}
            bins.append(entry)
        neighborhoods[family]=bins
        positive_families += int(any(all(bins[start+offset]["B1_SHIELDED_PI0"]["positive"] and bins[start+offset][best_simple]["positive"] for offset in range(3)) for start in range(6)))
    return {"integrity":"PASS","paired_n":len(rows),"best_simple_comparator":best_simple,"paired_primary_delta_vs_comparator":{method:_mean(values) for method,values in paired.items()},"paired_median_delta_vs_comparator":{method:median(values) for method,values in paired.items()},"regime_paired_primary_deltas":regime,"density_bin_neighborhoods":neighborhoods,"macro_m1_gt_b1":_mean(paired["B1_SHIELDED_PI0"])>0,"macro_m1_gt_ratio":_mean(paired["B4_RATIO_PSVR"])>0,"macro_m1_gt_best_simple":_mean(paired[best_simple])>0,"continuous_positive_families_at_least_two":positive_families>=2,"evaluated_without_posthoc_selection":True}

def emit_frozen_decision_branch(gate: dict) -> dict:
    if gate.get("integrity")!="PASS": branch="BLOCKED_EXECUTION_INTEGRITY"
    elif all(gate[key] for key in ("macro_m1_gt_b1","macro_m1_gt_ratio","macro_m1_gt_best_simple","continuous_positive_families_at_least_two")): branch="ACCEPT_IDEAL_MECHANISM"
    else: branch="REJECT"
    return {"hypothesis_id":"H-ROLLOUT1A-R2","final_branch":branch,"integrity_status":gate.get("integrity"),"frozen_gate_reconstructed":True}
