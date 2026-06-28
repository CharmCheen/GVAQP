#!/usr/bin/env python3
"""Diversity prefilter replay v1 — read-only simulation on V13.7 proxy features
and V13.8 oracle labels. No new model calls.

Hypotheses being tested (vs V13.9/V13.10 single-axis proxy-top-B baseline):
  H1. Prefilter diversity: top-P (P>k*B) proxy pool -> greedy diversity cover
      (temporal-spread-aware) -> B oracle calls. Beats static top-B at fixed B.
  H2. Multi-signal max-pool: max over {object_count_mean, bottom_roi_vehicle_count,
      yolo_vehicle_max, motion_energy_max} z-scores. Captures heterogeneous
      object classes (vehicle/pedestrian/cyclist) better than any single proxy.
  H3. Confirmed-positive adaptive refine: oracle round 1 on top-(B/2) proxy picks;
      for each TRUE positive returned, replay oracle on adjacent anchors within
      +-30s for free (label-known replay); total oracle calls == B. Beats static
      top-B at fixed B because it switches adapt rule from "proxy score boost"
      to "explore around confirmed positives".

All methods use the SAME event-overlap definition as V13.9
(`start_time`/`end_time` window of the anchor intersecting event [start,end])
so numbers are directly comparable to v13_9 tables.
"""
import csv, json, os, sys, math, random, statistics, time
from collections import defaultdict
import numpy as np

# ---- paths ----
ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/diversity_prefilter_replay_v1"
V13_8 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_8_center10_full_oracle_reference_v1"
V13_7 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_7_center10_multi_method_replay_v1"
V13_9 = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1"
ORACLE_LABELS = f"{V13_8}/tables/center10_full_oracle_labels.csv"
ORACLE_EVENTS = f"{V13_8}/tables/center10_vlm_oracle_events.csv"
PROXY_CSV = f"{V13_7}/tables/center10_proxy_features.csv"
V13_9_RESULTS = f"{V13_9}/tables/method_budget_results.csv"

SEED = 42
N_RANDOM_REPEATS = 200
VIDEO_DURATION_SECONDS = 3987.104  # same as V13.9
BUDGETS = [5, 10, 20, 40, 80]

# ---- load inputs ----
oracle_rows = list(csv.DictReader(open(ORACLE_LABELS)))
events_rows = list(csv.DictReader(open(ORACLE_EVENTS)))
proxy_rows = list(csv.DictReader(open(PROXY_CSV)))
v13_9_results = list(csv.DictReader(open(V13_9_RESULTS)))

proxy = {r["anchor_id"]: r for r in proxy_rows}
anchor_list = sorted(proxy.keys())
n_total = len(anchor_list)

# anchor -> oracle label row
oracle_by_id = {r["anchor_id"]: r for r in oracle_rows}
anchor_pos = {a: (oracle_by_id[a]["label"] == "positive") for a in anchor_list}
total_pos_anchors = sum(anchor_pos.values())

events = []
for e in events_rows:
    events.append({
        "event_id": e["event_id"],
        "start": float(e["event_start"]),
        "end": float(e["event_end"]),
        "type": e.get("event_type_majority", ""),
    })
total_events = len(events)

# event overlap (same as V13.9): anchor window = [start_time, end_time]
def event_hits(selected):
    hit_overlap, hit_iou03, hit_iou05 = set(), set(), set()
    for aid in selected:
        r = oracle_by_id[aid]
        a_start = float(r["start_time"]); a_end = float(r["end_time"])
        if r.get("event_start_absolute", "") and r.get("event_end_absolute", ""):
            try:
                a_start = float(r["event_start_absolute"]) - 1.0
                a_end = float(r["event_end_absolute"]) + 1.0
            except Exception:
                pass
        for ev in events:
            ov = max(0.0, min(a_end, ev["end"]) - max(a_start, ev["start"]))
            if ov > 0:
                hit_overlap.add(ev["event_id"])
                union = max(a_end, ev["end"]) - min(a_start, ev["start"])
                iou = ov / union if union > 0 else 0
                if iou >= 0.3: hit_iou03.add(ev["event_id"])
                if iou >= 0.5: hit_iou05.add(ev["event_id"])
    return len(hit_overlap), len(hit_iou03), len(hit_iou05)

# ---- z-score normalization (over all 399 anchors, same as V13.7 score_* features) ----
def z(col):
    vals = np.array([float(proxy[a][col]) for a in anchor_list], dtype=float)
    mu, sd = float(vals.mean()), float(vals.std(ddof=0))
    if sd == 0: sd = 1.0
    return {a: (float(proxy[a][col]) - mu) / sd for a in anchor_list}

Z_OBJ_MEAN = z("object_count_mean")
Z_OBJ_MAX  = z("object_count_max")
Z_VEH_MAX  = z("yolo_vehicle_max")
Z_VEH_MEAN = z("yolo_vehicle_mean")
Z_BBOX     = z("bbox_area_sum_max")
Z_BBOXAREA = z("max_bbox_area_max")
Z_BOTTOM   = z("bottom_roi_vehicle_count_mean")
Z_CENTER   = z("center_roi_vehicle_count_mean")
Z_MOT      = z("motion_energy_max")
Z_MOTS     = z("motion_energy_sum")

# =============================================================================
# Method definitions
# =============================================================================

def select_uniform(B):
    step = max(1, n_total // B)
    return [anchor_list[i] for i in range(0, n_total, step)][:B]

def select_random(B, seed):
    rng = random.Random(seed)
    idx = list(range(n_total)); rng.shuffle(idx)
    return [anchor_list[i] for i in idx[:B]]

def select_topB(score_dict, B):
    return sorted(anchor_list, key=lambda a: score_dict[a], reverse=True)[:B]

def select_prefilter_diversity(score_dict, B, P_mult, alpha):
    """top-P proxy pool, then greedily pick B to maximize score - alpha*min_dist_to_selected."""
    P = min(n_total, P_mult * B)
    pool = sorted(anchor_list, key=lambda a: score_dict[a], reverse=True)[:P]
    if B >= len(pool): return pool[:B]
    selected = [pool[0]]
    times = {a: float(proxy[a]["anchor_time"]) for a in pool}
    while len(selected) < B:
        best, best_val = None, -1e18
        for a in pool:
            if a in selected: continue
            min_d = min(abs(times[a] - times[s]) for s in selected)
            val = score_dict[a] + alpha * min_d
            if val > best_val: best_val, best = val, a
        selected.append(best)
    return selected

def select_multi_signal_max(B, weights):
    """max over weighted z-scores of multiple features."""
    cols = list(weights.keys())
    def score(a):
        return max(weights[c] * zmap[c][a] for c in cols)
    zmap = {"object_count_mean": Z_OBJ_MEAN, "object_count_max": Z_OBJ_MAX,
            "yolo_vehicle_max": Z_VEH_MAX, "bottom_roi_vehicle_count_mean": Z_BOTTOM,
            "motion_energy_max": Z_MOT, "center_roi_vehicle_count_mean": Z_CENTER}
    s = {a: max(weights[c] * zmap[c][a] for c in cols) for a in anchor_list}
    return select_topB(s, B), s

def select_confirmed_positive_refine(score_dict, B, refine_radius=30.0):
    """Round 1: top-(B/2) proxy; for each TRUE positive, replay +-radius anchors
    as oracle round 2 until total calls == B. Uses oracle labels (replay)."""
    round1 = max(1, B // 2)
    stage1 = select_topB(score_dict, round1)
    confirmed = [a for a in stage1 if anchor_pos[a]]
    calls = list(stage1)
    times = {a: float(proxy[a]["anchor_time"]) for a in anchor_list}
    by_time = sorted(anchor_list, key=lambda a: times[a])
    # candidate neighbors around each confirmed positive, excluding already-called
    candidates = []
    for c in confirmed:
        tc = times[c]
        for a in by_time:
            if a in calls: continue
            if abs(times[a] - tc) <= refine_radius:
                # prefer closer
                candidates.append((abs(times[a] - tc), -score_dict[a], a))
    # sort by (closer, higher score)
    candidates.sort()
    budget_remaining = B - len(calls)
    for _, _, a in candidates[:budget_remaining]:
        calls.append(a)
    if len(calls) < B:
        # fill remaining with next top proxy not yet called
        rest = [a for a in select_topB(score_dict, n_total) if a not in calls]
        calls.extend(rest[:B - len(calls)])
    return calls[:B]

# object_type_conditioned (oracle-blind): max over per-class best feature proxies
# we approximate pedestrian signal by motion_energy (high AUC=0.704 for ped)
# and cyclist/vehicle by object_count / yolo_vehicle_max (AUC 0.728/0.693)
OTC_WEIGHTS = {
    "object_count_mean": 1.0,   # all-class
    "yolo_vehicle_max": 1.0,     # vehicle strong
    "bottom_roi_vehicle_count_mean": 1.0,  # lateral / side intrusion
    "motion_energy_max": 1.0,   # pedestrian strong
}

def score_otc(a):
    zmap = {"object_count_mean": Z_OBJ_MEAN, "yolo_vehicle_max": Z_VEH_MAX,
            "bottom_roi_vehicle_count_mean": Z_BOTTOM, "motion_energy_max": Z_MOT}
    return max(OTC_WEIGHTS[c] * zmap[c][a] for c in OTC_WEIGHTS)

def select_otc(B):
    s = {a: score_otc(a) for a in anchor_list}
    return select_topB(s, B)

# simple fusion (V13.9 already has) for completeness / sanity
def select_fusion_geom_motion(B):
    return select_topB({a: float(proxy[a]["score_fusion_geometry_motion"]) for a in anchor_list}, B)

# =============================================================================
# Sanity checks
# =============================================================================
sanity = []
def sanity_check():
    # 1) uniform count = B
    for B in [5, 20, 80]:
        s = select_uniform(B)
        assert len(s) == B, f"uniform B={B} got {len(s)}"
    # 2) object_count_mean top-20 vs V13.9 best (should be near V13.9's 0.137; V13.9 didn't test object_count_top)
    # but at least: top_yolo_vehicle_max B=20 should match V13.9 number ~6 events
    s = select_topB(Z_VEH_MAX, 20)
    hits = event_hits(s)[0]
    v13_9_ymax_b20 = next((int(r["events_hit_overlap"]) for r in v13_9_results
                            if r["method"]=="top_yolo_vehicle_max" and r["B32"]=="20"), None)
    sanity.append(f"top_yolo_vehicle_max B=20 events_hit (mine)={hits} (V13.9={v13_9_ymax_b20})")
    # allow ±1 (window overlap exactness / tie-breaking)
    if v13_9_ymax_b20 is not None and abs(hits - v13_9_ymax_b20) <= 1:
        sanity.append(f"SANITY_OK: top_yolo_vehicle_max within +-1 of V13.9")
    else:
        sanity.append(f"SANITY_WARN: top_yolo_vehicle_max differs by {abs(hits-(v13_9_ymax_b20 or 0))}")
    # 3) positive_anchor count check
    assert total_pos_anchors == 94, f"expected 94 positives, got {total_pos_anchors}"
    assert total_events == 51, f"expected 51 events, got {total_events}"
    # 4) OracleBest@B = min(B,51)/51
    for B in [20, 40, 80]:
        ob = min(B, 51) / 51
        sanity.append(f"OracleBest@B={B} = {ob:.3f}")
sanity_check()

# =============================================================================
# Evaluation
# =============================================================================
def evaluate(method_name, selected, B):
    pos_sel = sum(1 for a in selected if anchor_pos[a])
    ev_hit, ev_i3, ev_i5 = event_hits(selected)
    recall = ev_hit / total_events
    coarse_dur = len(selected) * 10.0
    return {
        "method": method_name, "B": str(B),
        "num_selected_anchors": len(selected),
        "positive_anchors_selected": pos_sel,
        "positive_anchor_precision": pos_sel / max(1, len(selected)),
        "positive_anchor_recall": pos_sel / total_pos_anchors,
        "events_hit_overlap": ev_hit,
        "events_hit_iou_0p3": ev_i3,
        "events_hit_iou_0p5": ev_i5,
        "event_count_total": total_events,
        "event_recall_overlap": recall,
        "event_recall_iou_0p3": ev_i3 / total_events,
        "event_recall_iou_0p5": ev_i5 / total_events,
        "returned_duration_coarse_seconds": coarse_dur,
        "returned_duration_fraction_coarse": coarse_dur / VIDEO_DURATION_SECONDS,
        "positive_anchor_base_rate": total_pos_anchors / n_total,
        "claim_scope": "FULL_CENTER10_ORACLE_RELATIVE_SINGLE_VIDEO",
    }

# score maps for reuse
score_obj_mean = {a: float(proxy[a]["object_count_mean"]) for a in anchor_list}
score_yolo_max = {a: float(proxy[a]["yolo_vehicle_max"]) for a in anchor_list}
score_fusion  = {a: float(proxy[a]["score_fusion_geometry_motion"]) for a in anchor_list}

# build all method invocations
configs = []
# baselines (sanity)
configs.append(("uniform_anchor_10s",     lambda B: select_uniform(B)))
configs.append(("top_yolo_vehicle_max",    lambda B: select_topB(score_yolo_max, B)))
configs.append(("top_object_count_mean",   lambda B: select_topB(score_obj_mean, B)))
configs.append(("top_fusion_geometry_motion", lambda B: select_topB(score_fusion, B)))
configs.append(("top_otc_multisignal_max", lambda B: select_otc(B)))

# H1: prefilter diversity (using strongest single feature object_count_mean)
for P_mult in [2, 3, 4, 8]:
    for alpha in [0.5, 1.0, 2.0]:
        name = f"prefilter_div_objmean_P{P_mult}B_a{alpha}"
        configs.append((name, lambda B, P=P_mult, a=alpha: select_prefilter_diversity(score_obj_mean, B, P, a)))

# H1b: same prefilter diversity but on yolo_vehicle_max (V13.9 proxy)
for P_mult in [2, 4]:
    for alpha in [1.0, 2.0]:
        name = f"prefilter_div_yolomax_P{P_mult}B_a{alpha}"
        configs.append((name, lambda B, P=P_mult, a=alpha: select_prefilter_diversity(score_yolo_max, B, P, a)))

# H2: multi-signal max (already as otc)
# also try variants
configs.append(("multisignal_obj_veh_bottom", lambda B: select_topB(
    {a: max(Z_OBJ_MEAN[a], Z_VEH_MAX[a], Z_BOTTOM[a]) for a in anchor_list}, B)))
configs.append(("multisignal_obj_veh_bottom_mot", lambda B: select_topB(
    {a: max(Z_OBJ_MEAN[a], Z_VEH_MAX[a], Z_BOTTOM[a], Z_MOT[a]) for a in anchor_list}, B)))

# H3: confirmed positive refine on object_count and yolo
for base_name, base_sc in [("objmean", score_obj_mean), ("yolomax", score_yolo_max)]:
    for r in [20.0, 30.0, 60.0]:
        name = f"refine_pos_confirmed_{base_name}_r{int(r)}"
        configs.append((name, lambda B, sc=base_sc, rr=r: select_confirmed_positive_refine(sc, B, rr)))

# Run all + random repeats
random.seed(SEED); np.random.seed(SEED)
t0 = time.time()
results, selections = [], []
for name, fn in configs:
    for B in BUDGETS:
        sel = fn(B)
        if len(sel) != B:
            # shouldn't happen except round1 vs round2 edge cases; clip
            sel = sel[:B] if len(sel) > B else sel + [a for a in anchor_list if a not in sel][:B-len(sel)]
        r = evaluate(name, sel, B)
        results.append(r)
        for a in sel:
            selections.append({"method": name, "B": str(B), "anchor_id": a, "is_positive": str(anchor_pos[a])})

# random baseline: 200 repeats per B
rand_by_B = defaultdict(list)
for B in BUDGETS:
    for rep in range(N_RANDOM_REPEATS):
        seed = SEED + rep
        sel = select_random(B, seed)
        r = evaluate(f"random_seed{seed}", sel, B)
        r["method"] = "random_baseline"
        results.append(r)
        rand_by_B[B].append(r["event_recall_overlap"])

# random summary
rand_summary = []
for B in sorted(rand_by_B.keys()):
    vals = np.array(rand_by_B[B])
    rand_summary.append({
        "B": str(B), "n_repeats": len(vals),
        "mean": float(vals.mean()), "std": float(vals.std(ddof=1)),
        "p2_5": float(np.percentile(vals, 2.5)),
        "p97_5": float(np.percentile(vals, 97.5)),
        "min": float(vals.min()), "max": float(vals.max()),
    })

# ---- write tables ----
def write_csv(path, rows, extras=None):
    if not rows: return
    keys = list(rows[0].keys())
    if extras: keys = keys + extras
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

write_csv(f"{ROOT}/tables/method_budget_results.csv", results)
write_csv(f"{ROOT}/tables/method_selected_anchors.csv", selections)
write_csv(f"{ROOT}/tables/random_baseline_summary.csv", rand_summary)

# best-by-budget (excluding random)
non_rand = [r for r in results if r["method"] != "random_baseline"]
best_by = []
for B in BUDGETS:
    sub = [r for r in non_rand if int(r["B"]) == B]
    if not sub: continue
    best = max(sub, key=lambda r: float(r["event_recall_overlap"]))
    rs = next(rs for rs in rand_summary if rs["B"] == str(B))
    entry = dict(best)
    entry["random_mean"] = rs["mean"]; entry["random_std"] = rs["std"]
    entry["random_p97_5"] = rs["p97_5"]
    entry["delta_vs_random_mean"] = float(best["event_recall_overlap"]) - rs["mean"]
    best_by.append(entry)
write_csv(f"{ROOT}/tables/best_methods_by_budget.csv", best_by)

# H1, H2, H3 per-method delta table (excluding baselines & random)
baseline_methods = {"uniform_anchor_10s", "top_yolo_vehicle_max", "top_object_count_mean",
                    "top_fusion_geometry_motion", "top_otc_multisignal_max",
                    "multisignal_obj_veh_bottom", "multisignal_obj_veh_bottom_mot"}
h_methods = [r for r in non_rand if r["method"] not in baseline_methods]
write_csv(f"{ROOT}/tables/h_method_results.csv", h_methods)

# delta summary table: max H1/H2/H3 method per B
def best_in(prefix, B):
    sub = [r for r in non_rand if r["method"].startswith(prefix) and int(r["B"]) == B]
    return max(sub, key=lambda r: float(r["event_recall_overlap"])) if sub else None

delta_rows = []
for B in BUDGETS:
    rs = next(rs for rs in rand_summary if rs["B"] == str(B))
    base_top_obj = next(r for r in non_rand if r["method"]=="top_object_count_mean" and int(r["B"])==B)
    base_yolo = next(r for r in non_rand if r["method"]=="top_yolo_vehicle_max" and int(r["B"])==B)
    row = {"B": str(B), "random_mean": rs["mean"], "random_p97_5": rs["p97_5"],
           "top_obj_mean_recall": base_top_obj["event_recall_overlap"],
           "top_yolo_max_recall": base_yolo["event_recall_overlap"]}
    for tag in ["prefilter_div_", "multisignal_", "refine_pos_confirmed_"]:
        bb = best_in(tag, B)
        if bb:
            row[f"best_{tag.strip('_')}_method"] = bb["method"]
            row[f"best_{tag.strip('_')}_recall"] = bb["event_recall_overlap"]
            row[f"best_{tag.strip('_')}_delta_vs_random"] = float(bb["event_recall_overlap"]) - rs["mean"]
            row[f"best_{tag.strip('_')}_delta_vs_objmean"] = float(bb["event_recall_overlap"]) - float(base_top_obj["event_recall_overlap"])
    delta_rows.append(row)
write_csv(f"{ROOT}/tables/delta_summary.csv", delta_rows)

# Sanity log
with open(f"{ROOT}/logs/sanity_and_run.log", "w") as f:
    f.write("SANITY CHECKS:\n")
    for s in sanity: f.write(s + "\n")
    f.write(f"\nOracle positives: {total_pos_anchors}/{n_total} anchors ({total_pos_anchors/n_total:.3f})\n")
    f.write(f"Oracle events: {total_events}\n")
    f.write(f"N_random_repeats: {N_RANDOM_REPEATS}, seed_base: {SEED}\n")
    f.write(f"Wall time: {time.time()-t0:.2f}s\n")
    f.write(f"Input files:\n  {ORACLE_LABELS}\n  {ORACLE_EVENTS}\n  {PROXY_CSV}\n  {V13_9_RESULTS}\n")

# Print key results
print("="*70)
print("SANITY:")
for s in sanity: print("  "+s)
print("\nRANDOM BASELINE (%d repeats):"%N_RANDOM_REPEATS)
for rs in rand_summary:
    print(f"  B={rs['B']:>3s}: mean={rs['mean']:.3f} std={rs['std']:.3f} 95% CI=[{rs['p2_5']:.3f},{rs['p97_5']:.3f}] min={rs['min']:.3f} max={rs['max']:.3f}")
print("\nBEST PER BUDGET (non-random):")
for bb in best_by:
    print(f"  B={bb['B']:>3s}: best={bb['method']:40s} recall={float(bb['event_recall_overlap']):.3f}  rand_mean={float(bb['random_mean']):.3f}  delta={float(bb['delta_vs_random_mean']):+.3f}")
print("\nDelta summary (H1/H2/H3 vs random and vs top_object_count_mean):")
for dr in delta_rows:
    print(f"  B={dr['B']:>3s}: random={float(dr['random_mean']):.3f}  objmean={float(dr['top_obj_mean_recall']):.3f}  yolo_max={float(dr['top_yolo_max_recall']):.3f}")
    for tag in ["prefilter_div", "multisignal", "refine_pos_confirmed"]:
        if f"best_{tag}_recall" in dr:
            print(f"      {tag:25s}: recall={float(dr[f'best_{tag}_recall']):.3f}  Δrand={float(dr[f'best_{tag}_delta_vs_random']):+.3f}  Δobjmean={float(dr[f'best_{tag}_delta_vs_objmean']):+.3f}")

# ---- DECISION ----
# Pass criteria: any H method beats random AND beats baselines at B=20 and B=40
b20 = next(dr for dr in delta_rows if dr["B"]=="20")
b40 = next(dr for dr in delta_rows if dr["B"]=="40")
best_h20 = max(
    float(b20.get(f"best_{t}_recall", 0)) for t in ["prefilter_div","multisignal","refine_pos_confirmed"]
)
best_h40 = max(
    float(b40.get(f"best_{t}_recall", 0)) for t in ["prefilter_div","multisignal","refine_pos_confirmed"]
)
rand20 = float(b20["random_mean"])
rand40 = float(b40["random_mean"])
rand20_p97 = float(b20["random_p97_5"])
rand40_p97 = float(b40["random_p97_5"])
base20 = float(b20["top_obj_mean_recall"])
base40 = float(b40["top_obj_mean_recall"])

# Strong: best H beats random 97.5th percentile AND beats base
# Weak: beats random mean by >= 0.05 AND >= base
# None: otherwise
strong20 = best_h20 > rand20_p97 and best_h20 > base20
weak20 = (best_h20 - rand20) >= 0.05 and best_h20 > base20
strong40 = best_h40 > rand40_p97 and best_h40 > base40
weak40 = (best_h40 - rand40) >= 0.05 and best_h40 > base40

if strong20 and strong40:
    decision = "STRONG_GO"
elif weak20 or weak40:
    decision = "WEAK_GO"
else:
    decision = "NO_GO"

dec = {
    "decision": decision,
    "best_h_recall_B20": best_h20, "best_h_recall_B40": best_h40,
    "random_mean_B20": rand20, "random_p97_5_B20": rand20_p97, "random_mean_B40": rand40, "random_p97_5_B40": rand40_p97,
    "base_objmean_recall_B20": base20, "base_objmean_recall_B40": base40,
    "strong_B20": strong20, "strong_B40": strong40, "weak_B20": weak20, "weak_B40": weak40,
    "n_random_repeats": N_RANDOM_REPEATS, "seed": SEED,
    "scope": "FULL_CENTER10_ORACLE_RELATIVE_SINGLE_VIDEO (realcartest.mp4 66.5min)",
}
with open(f"{ROOT}/tables/decision.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(dec.keys())); w.writeheader(); w.writerow(dec)
print("\n"+"="*70); print("DECISION:", decision)
for k,v in dec.items():
    if k not in ("decision","scope","seed","n_random_repeats"):
        print(f"  {k}: {v}")