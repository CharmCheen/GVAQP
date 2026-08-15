#!/usr/bin/env python3
"""CPU-only, stdlib-only deterministic re-verification of key GVAQP numbers.

No model loading, no inference, no network. Reads frozen CSVs/JSONs only.
Companion record: VERIFICATION_RESULTS.json
"""
import csv, hashlib, json, os, statistics as st
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "outputs")
results = []

def rows_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def med(vals): return st.median(vals)

def check(name, computed, expected, note="", tol=1e-9):
    ok = (computed == expected) if isinstance(expected, (str, dict, tuple, list)) else abs(float(computed) - float(expected)) <= tol
    results.append({"check": name, "computed": computed, "expected": expected, "ok": ok, "note": note})
    print(f"[{'OK' if ok else 'FAIL'}] {name}: computed={computed} expected={expected} {note}")

# ---------- P0 V3 materializer ----------
pairs = rows_csv(os.path.join(OUT, "p0_materializer_validation_v3/controlled_pairs.csv"))
valid = [r for r in pairs if r["valid_controlled_pair"] == "True"]
by_key = defaultdict(dict)
for r in pairs:
    k = (r["video_id"], r["query_id"], r["budget"], r["seed"], r["selector"])
    by_key[k][r["materializer"]] = r
deltas = []; per_video = defaultdict(list); per_sel = defaultdict(list)
better = equal = worse = 0
for k, d in by_key.items():
    f0, f3 = float(d["K0"]["F1"]), float(d["K3"]["F1"])
    delta = f3 - f0; deltas.append(delta)
    if delta > 1e-12: better += 1
    elif delta < -1e-12: worse += 1
    else: equal += 1
    per_video[k[0]].append(delta); per_sel[k[4]].append(delta)
check("p0_valid_rows", len(valid), 108)
check("p0_pair_count", len(deltas), 54)
check("p0_k3_better_equal_worse", {"better": better, "equal": equal, "worse": worse}, {"better": 40, "equal": 14, "worse": 0})
check("p0_median_delta_f1", round(med(deltas), 4), 0.1457, tol=1e-3)
check("p0_mean_delta_f1", round(st.mean(deltas), 4), 0.1840, tol=1e-3)
check("p0_per_video_medians", {k: round(med(v),4) for k,v in per_video.items()},
      {"DALI": 0.1377, "HANGZHOU": 0.1441, "WUHAN": 0.1675}, tol=1e-3)
check("p0_per_selector_medians", {k: round(med(v),4) for k,v in per_sel.items()},
      {"UniformTemporal": 0.1813, "StaticProxyRank": 0.2704, "TemporalCoverage": 0.0182}, tol=1e-3)

# ---------- Mechanism ablation ----------
mech = rows_csv(os.path.join(OUT, "p0_materializer_mechanism_ablation_v1/mechanism_effects.csv"))
mech_med = defaultdict(list); mech_pm = defaultdict(Counter)
for r in mech:
    m = r["mechanism"]; d = float(r["Delta_F1"]); mech_med[m].append(d)
    if d > 1e-12: mech_pm[m]["+"] += 1
    elif d < -1e-12: mech_pm[m]["-"] += 1
    else: mech_pm[m]["="] += 1
check("mech_gap_median", round(med(mech_med["gap constraint"]),4), 0.1377, tol=1e-3)
check("mech_gap_pm", dict(mech_pm["gap constraint"]), {"+": 40, "=": 14})
check("mech_duration_median", med(mech_med["duration cap"]), 0.0)
check("mech_barrier_median", med(mech_med["queried-negative barrier"]), 0.0)
check("mech_k3extras_median", med(mech_med["current-V3 unknown/parse/exact semantics"]), 0.0)

# ---------- Alignment: ranking vs exposure gap (exact frozen definition) ----------
matrix = rows_csv(os.path.join(OUT, "main_thesis_alignment_v1/QUERY_POLICY_MATRIX.csv"))
VIDEOS = ("DALI", "HANGZHOU", "WUHAN"); POLICIES = ("UniformTemporal", "StaticProxyRank", "TemporalCoverage")
def value(regime, policy, video, budget):
    for r in matrix:
        if r["video_id"]==video and r["proxy_regime"]==regime and r["policy"]==policy and int(r["budget"])==budget:
            return float(r["F1"])
    raise KeyError((regime,policy,video,budget))
rank_pairs = [value("R0_ORIGINAL","StaticProxyRank",v,b) - value("R3_RANK_SEVERE_HASH","StaticProxyRank",v,b) for v in VIDEOS for b in (5,10,20)]
exposure_pairs = [value("R0_ORIGINAL",p,v,b) - value("E3_EXPOSURE_SEVERE_KEEP040",p,v,b) for v in VIDEOS for b in (5,10,20) for p in POLICIES]
check("rank_low_budget_median_gap", med(rank_pairs), 0.09513395297977037)
check("exposure_low_budget_median_gap", med(exposure_pairs), 0.0)

# ---------- Monotonicity ----------
mono = rows_csv(os.path.join(OUT, "main_thesis_alignment_v1/RESOURCE_MONOTONICITY.csv"))
nested = [r for r in mono if r["nested_budget_trace"] == "True" and r["primary_anytime_interpretation"] == "True"]
tot_t = sum(int(r["transition_count"]) for r in nested); tot_v = sum(int(r["violation_count"]) for r in nested)
check("nested_monotonicity_violation_rate", round(tot_v/tot_t, 6), 0.004762, tol=1e-5)

# ---------- Proxy quality ----------
pq = rows_csv(os.path.join(OUT, "main_thesis_alignment_v1/PROXY_QUALITY_METRICS.csv"))
auprc = {v: round(float([x for x in pq if x["video_id"]==v and x["regime"]=="R0_ORIGINAL"][0]["ranking_AUPRC_conditional_on_exposure"]),4) for v in VIDEOS}
check("proxy_auprc_by_video", auprc, {"DALI": 0.3146, "HANGZHOU": 0.2584, "WUHAN": 0.3112}, tol=1e-3)
units = sum(int([x for x in pq if x["video_id"]==v and x["regime"]=="R0_ORIGINAL"][0]["total_units"]) for v in VIDEOS)
check("total_units", units, 1475)
cands = sum(int([x for x in pq if x["video_id"]==v and x["regime"]=="R0_ORIGINAL"][0]["candidate_rows"]) for v in VIDEOS)
check("total_candidates", cands, 1475)
pos = sum(int([x for x in pq if x["video_id"]==v and x["regime"]=="R0_ORIGINAL"][0]["total_positive_units"]) for v in VIDEOS)
check("semantic_positive_units", pos, 251)
all_one = all(float([x for x in pq if x["video_id"]==v and x["regime"]=="R0_ORIGINAL"][0]["structural_candidate_exposure_recall"])==1.0 for v in VIDEOS)
check("structural_exposure_recall_all_one", all_one, True)

# ---------- 108-state decompositions ----------
diag = rows_csv(os.path.join(OUT, "original_theory_identifiability_audit_v1/Q_OBJECTIVE_STATE_DIAGNOSTIC.csv"))
check("q108_original_classes", dict(Counter(r["original_class"] for r in diag)), {"BENEFICIAL": 5, "HARMFUL": 5, "INDIFFERENT": 98})
check("q108_smooth_classes", dict(Counter(r["smooth_class"] for r in diag)), {"BENEFICIAL": 5, "HARMFUL": 4, "INDIFFERENT": 99})
branches = [json.loads(l) for l in open(os.path.join(OUT, "controller_dynamic_headroom_cached_reproduction_v1/STATE_ACTION_BRANCHES.jsonl")) if l.strip()]
check("branch_record_count", len(branches), 108)
sb = sum(1 for b in branches if b["delta_q"] > 1e-12); vb = sum(1 for b in branches if b["delta_q"] < -1e-12)
check("branch_scan_verify_tied_split", {"SCAN": sb, "VERIFY": vb, "TIED": len(branches)-sb-vb}, {"SCAN": 25, "VERIFY": 26, "TIED": 57})

# ---------- Public-state predictability ----------
ps = json.load(open(os.path.join(OUT, "public_state_predictability_cached_v3/SUMMARY.json")))
check("psp_best_learned_regret", round(ps["best_learned_decision_regret"], 6), 0.009693, tol=1e-5)
check("psp_best_fixed_regret", round(ps["best_fixed_action_decision_regret"], 6), 0.000885, tol=1e-5)
check("psp_state_count", ps["state_count"], 108)
check("psp_source_videos", ps["source_video_count"], 2)
check("psp_gate_pass", ps["cached_public_state_gate_pass"], False)

# ---------- Shadow ----------
sd = json.load(open(os.path.join(OUT, "p1_shadow_vlm_direct_reference_v1/SHADOW_DECISION.json")))
check("shadow_exact_yield_pairs", sd["exact_yield_pairs"], 198)
check("shadow_clusters_pos_zero_neg", (sd["positive_clusters"], sd["zero_clusters"], sd["negative_clusters"]), (2,2,2))
check("shadow_macro_coverage_effect", round(sd["primary_mean_delta_event_coverage"], 6), 0.003193, tol=1e-5)
check("shadow_yolo_effect", round(sd["proxy_effects"]["PROXY_A_YOLOV8N_OBJECT_MOTION"], 6), -0.004974, tol=1e-5)
check("shadow_flow_effect", round(sd["proxy_effects"]["PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS"], 6), 0.009136, tol=1e-5)
check("shadow_geometry_mae_gain", round(sd["geometry_mae_added_value"], 6), 0.000665, tol=1e-5)
check("shadow_c1_pair_mean_delta_f1", round(sd["c1_pair_mean_delta_f1"], 6), -0.001026, tol=1e-5)
check("shadow_vlm_agreement_matched_fraction", round(sd["vlm_agreement"]["global_matched_event_fraction_iou_gt_0"], 3), 0.313, tol=1e-2)

# ---------- Geometry LOVO macro R2 ----------
lovo = rows_csv(os.path.join(OUT, "event_evidence_geometry_v1/LOVO_RESULTS.csv"))
macro = {}
for m in sorted(set(r["model"] for r in lovo)):
    per_vid = []
    for v in VIDEOS:
        sub = [r for r in lovo if r["model"]==m and r["heldout_video"]==v]
        y = [float(r["EventF1_C1"]) for r in sub]; p = [float(r["prediction"]) for r in sub]
        ym = st.mean(y)
        ss_res = sum((a-b)**2 for a,b in zip(y,p)); ss_tot = sum((a-ym)**2 for a in y)
        per_vid.append(1 - ss_res/ss_tot if ss_tot > 0 else float('nan'))
    macro[m] = round(st.mean(per_vid), 4)
check("geometry_lovo_macro_r2", macro, {"YIELD_ONLY": 0.0057, "YIELD_PLUS_PUBLIC_ONLINE_GEOMETRY": 0.7953, "REFERENCE_AWARE_DIAGNOSTIC_UPPER": 0.9803}, tol=1e-3)

# ---------- P2 ----------
p2_md = open(os.path.join(OUT, "p2_query_policy_novelty_killer_v1/P2_DECISION.md")).read()
p2d = json.loads(p2_md.split("```json")[1].split("```")[0])
check("p2_median_cluster_delta_f1", p2d["median_cluster_delta_F1"], 0.0)
check("p2_semantic_state_residual", p2d["semantic_state_residual_label"], "ABSENT")
check("p2_decision", p2d["decision"], "INCONCLUSIVE")
cb = rows_csv(os.path.join(OUT, "p2_query_policy_novelty_killer_v1/CLUSTER_BOOTSTRAP.csv"))
if cb and "median" in cb[0]:
    deltas = [float(r["median"]) for r in cb if r["metric"] == "delta_f1"]
    if deltas: check("p2_bootstrap_median_delta_f1", round(st.median(deltas), 4), 0.0, tol=1e-3)

# ---------- P1 automated counts ----------
p1 = os.path.join(OUT, "gvaqp_long_horizon_p1_p3_v1")
for name, path, exp in (("p1_equal_yield_rows", "P1_AUTOMATED_MODEL_RELATIVE_EQUAL_YIELD_MATCHED.csv", 198),
                        ("p1_trace_rows", "P1_AUTOMATED_MODEL_RELATIVE_TRACE_ENDPOINTS.csv", 1008),
                        ("p1_cluster_rows", "P1_AUTOMATED_MODEL_RELATIVE_CLUSTER_SUMMARY.csv", 12)):
    n = sum(1 for _ in open(os.path.join(p1, path))) - 1
    check(name, n, exp)
oracle_n = len([f for f in os.listdir(os.path.join(p1, "qwen32_oracle/raw")) if f.endswith(".json")])
print(f"[INFO] qwen32_oracle raw records: {oracle_n}")

# ---------- Protocol hash verification (canonical json) ----------
def canon(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
for d, pf in (("main_thesis_alignment_v1", "AUDIT_PROTOCOL.json"),
              ("p0_materializer_validation_v3", "EXPERIMENT_PROTOCOL.json"),
              ("p0_materializer_mechanism_ablation_v1", "MECHANISM_PROTOCOL.json"),
              ("p2_query_policy_novelty_killer_v1", "P2_PROTOCOL.json")):
    p = json.load(open(os.path.join(OUT, d, pf)))
    claimed = open(os.path.join(OUT, d, "PROTOCOL_HASH.txt")).read().strip()
    actual = canon({k: v for k, v in p.items() if k not in {"created_at_utc", "protocol_hash"}})
    check(f"protocol_hash_{d}", actual[:16] + "...", claimed[:16] + "...", tol=0)
    check(f"protocol_hash_{d}_full", actual, claimed)

# ---------- Human P1 labels file status ----------
lp = os.path.join(p1, "human_reference_package/HUMAN_EVENT_LABELS.jsonl")
n = sum(1 for l in open(lp) if l.strip())
check("human_p1_label_rows", n, 0)
h = hashlib.sha256(open(lp, "rb").read()).hexdigest()
check("human_p1_labels_sha256_empty_file", h, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
hp2 = os.path.join(p1, "human_reference_package/HUMAN_REFERENCE_PROTOCOL.json")
h2 = hashlib.sha256(open(hp2, "rb").read()).hexdigest()
check("human_p1_protocol_file_sha256", h2, "62575b06598aa1240b43bf34503da544c5623dbd515ed5b6cf4ac6dc9f4f8b45")

# ---------- Endogenous scan preflight ----------
preflight = os.path.join(OUT, "endogenous_scan_preflight_v1")
check("endogenous_scan_preflight_dir_exists", os.path.isdir(preflight), False)

failed = [r for r in results if not r["ok"]]
print(f"\n=== {len(results)} checks, {len(failed)} failed ===")
for r in failed: print("FAILED:", r)
json.dump({"checks": results, "n_checks": len(results), "n_failed": len(failed)},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERIFICATION_RESULTS.json"), "w"), indent=2)
print("VERIFICATION_RESULTS.json written")
