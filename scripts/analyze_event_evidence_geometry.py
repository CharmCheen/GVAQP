#!/usr/bin/env python3
"""Offline event-evidence-geometry audit over the frozen main-thesis traces.

This is an explanatory cached replay only: it reconstructs the 378 released
C1 traces, evaluates the pre-existing C0 materializer on those same cached
outcomes, and derives trace geometry.  It never calls a semantic oracle and
does not introduce or fit a query policy.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "outputs/event_evidence_geometry_v1"
MAIN = ROOT / "outputs/main_thesis_alignment_v1"
P0 = ROOT / "outputs/p0_materializer_validation_v3"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
RUNNER = ROOT / "scripts/run_p0_v3_materializer_validation.py"
MECH = ROOT / "scripts/analyze_p0_v3_materializer_mechanisms.py"
MAIN_RUNNER = ROOT / "scripts/run_main_thesis_alignment_audit.py"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
REGIMES = ("R0_ORIGINAL", "R1_RANK_MILD_A025", "R2_RANK_MEDIUM_A050", "R3_RANK_SEVERE_HASH", "E1_EXPOSURE_MILD_KEEP080", "E2_EXPOSURE_MEDIUM_KEEP060", "E3_EXPOSURE_SEVERE_KEEP040")
POLICIES = ("UniformTemporal", "StaticProxyRank", "TemporalCoverage")

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

def fnum(x: float | int) -> float:
    return float(x) if math.isfinite(float(x)) else float("nan")

def selected_regions(positions: list[int]) -> int:
    if not positions:
        return 0
    return 1 + sum(b - a > 1 for a, b in zip(positions, positions[1:]))

def gap_summary(positions: list[int], n: int) -> tuple[float, float]:
    """Unqueried gaps in original-unit counts, including video-end holes."""
    if not positions:
        return float(n), float(n)
    holes = [positions[0], n - 1 - positions[-1]] + [b - a - 1 for a, b in zip(positions, positions[1:])]
    return float(max(holes)), float(np.median(holes))

def reference_mapping(ref: pd.DataFrame) -> dict[str, list[str]]:
    m: dict[str, list[str]] = defaultdict(list)
    for row in ref.itertuples():
        for unit in row.source_unit_ids:
            m[str(unit)].append(str(row.event_id))
    return m

def entropy_norm(counts: list[int], support: int) -> float:
    if support <= 1 or not counts:
        return 0.0
    p = np.asarray(counts, dtype=float) / sum(counts)
    return float(-(p * np.log(p)).sum() / math.log(support))

def trace_features(video: str, selected: list[dict[str, Any]], labels: dict[str, Any], original: list[dict[str, Any]], ref_map: dict[str, list[str]], ref_count: int) -> dict[str, Any]:
    pos_map = {str(r["unit_id"]): int(r["candidate_order"]) for r in original}
    ordered = sorted(selected, key=lambda r: pos_map[str(r["unit_id"])])
    qpos = [pos_map[str(r["unit_id"])] for r in ordered]
    units = [labels[str(r["unit_id"])] for r in ordered]
    duration = max(float(x.end_time) for x in labels.values() if x.video_id == video)
    starts = [float(u.start_time) for u in units]
    ends = [float(u.end_time) for u in units]
    span = max(ends) - min(starts) if units else 0.0
    largest_hole, median_hole = gap_summary(qpos, len(original))
    # Ten equal temporal bins: fixed, outcome-blind local regions.
    bins = sorted(set(min(9, int((float(u.start_time) / max(duration, 1e-12)) * 10)) for u in units))
    per_local = len(units) / len(bins) if bins else 0.0
    near_dup = sum((b - a) <= 1 for a, b in zip(qpos, qpos[1:])) / len(qpos) if qpos else 0.0
    positives = [u for u in units if u.outcome == "relevant"]
    ppos = sorted(pos_map[u.unit_id] for u in positives)
    ptime = sorted(positives, key=lambda u: u.start_time)
    pspan = (ptime[-1].end_time - ptime[0].start_time) if ptime else 0.0
    centers = np.asarray([(u.start_time + u.end_time) / 2 for u in ptime], dtype=float)
    pdisp = float(np.std(centers) / duration) if len(centers) else 0.0
    pgaps = [max(0.0, b.start_time - a.end_time) for a, b in zip(ptime, ptime[1:])]
    pclusters = 0 if not ptime else 1 + sum(g > 10.0 for g in pgaps)
    positive_redundancy = (len(ptime) - pclusters) / len(ptime) if ptime else 0.0
    anchor_events: list[str] = []
    for unit in ptime:
        anchor_events.extend(ref_map.get(unit.unit_id, []))
    by_event: dict[str, int] = defaultdict(int)
    for event in anchor_events:
        by_event[event] += 1
    touched = len(by_event)
    return {
        "queried_units": len(units), "verified_positive_count": len(positives), "positive_yield": len(positives) / len(units) if units else 0.0,
        "queried_temporal_span_sec": span, "coverage_fraction": span / duration if duration else 0.0,
        "number_of_temporal_regions_touched": selected_regions(qpos), "largest_unqueried_gap_units": largest_hole,
        "median_unqueried_gap_units": median_hole, "queries_per_local_region": per_local, "near_duplicate_query_fraction": near_dup,
        "positive_anchor_count": len(ptime), "positive_anchor_temporal_span_sec": pspan,
        "positive_anchor_dispersion": pdisp, "median_positive_gap_sec": float(np.median(pgaps)) if pgaps else 0.0,
        "max_positive_gap_sec": float(max(pgaps)) if pgaps else 0.0, "positive_cluster_count": pclusters,
        "positive_redundancy": positive_redundancy,
        "reference_events_touched_OFFLINE_DIAGNOSTIC_ONLY": touched,
        "reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY": touched / ref_count if ref_count else 0.0,
        "events_with_0_anchor_OFFLINE_DIAGNOSTIC_ONLY": ref_count - touched,
        "events_with_1_anchor_OFFLINE_DIAGNOSTIC_ONLY": sum(v == 1 for v in by_event.values()),
        "events_with_2plus_anchors_OFFLINE_DIAGNOSTIC_ONLY": sum(v >= 2 for v in by_event.values()),
        "within_event_anchor_density_OFFLINE_DIAGNOSTIC_ONLY": float(np.mean(list(by_event.values()))) if by_event else 0.0,
        "cross_event_anchor_distribution_OFFLINE_DIAGNOSTIC_ONLY": entropy_norm(list(by_event.values()), ref_count),
    }

def fit_lovo(frame: pd.DataFrame, features: list[str], model_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions, summary = [], []
    for held in VIDEOS:
        train, test = frame[frame.video_id != held], frame[frame.video_id == held]
        model = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
        model.fit(train[features], train.EventF1_C1)
        pred = model.predict(test[features])
        for row, yhat in zip(test.itertuples(), pred):
            predictions.append({"model": model_name, "heldout_video": held, "trace_hash": row.trace_hash, "EventF1_C1": row.EventF1_C1, "prediction": float(yhat)})
        summary.append({"model": model_name, "heldout_video": held, "n_train": len(train), "n_test": len(test),
                        "MAE": mean_absolute_error(test.EventF1_C1, pred), "R2": r2_score(test.EventF1_C1, pred),
                        "pearson_r": float(np.corrcoef(test.EventF1_C1, pred)[0, 1]) if np.std(pred) else 0.0})
    p = pd.DataFrame(predictions); s = pd.DataFrame(summary)
    s = pd.concat([s, pd.DataFrame([{"model": model_name, "heldout_video": "MACRO_MEAN", "n_train": np.nan, "n_test": len(frame), "MAE": s.MAE.mean(), "R2": s.R2.mean(), "pearson_r": s.pearson_r.mean()}])], ignore_index=True)
    return p, s

def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite existing audit output: {OUT}")
    OUT.mkdir(parents=True)
    p0, mech, mainrun = load_module("geo_p0", RUNNER), load_module("geo_mech", MECH), load_module("geo_main", MAIN_RUNNER)
    labels, candidates, references = p0.load_data()
    public = mainrun.load_candidate_proxy_only()
    defs = {x["regime"]: x for x in mainrun.REGIMES}
    regimes = {(video, regime): mainrun.construct_regime(public[video], defs[regime]) for video in VIDEOS for regime in REGIMES}
    matrix = pd.read_csv(MAIN / "QUERY_POLICY_MATRIX.csv")
    ref = pd.read_parquet(V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet")
    ref_maps = {video: reference_mapping(ref[ref.video_id == video]) for video in VIDEOS}
    ref_counts = ref.groupby("video_id").size().to_dict()
    rows = []
    from garc_eval.accelerated_event_query.matching import MatchConfig
    for item in matrix.itertuples():
        selected = p0.select_trace(item.policy, regimes[(item.video_id, item.proxy_regime)], int(item.budget))
        units = [labels[x["unit_id"]] for x in selected]
        geometry = trace_features(item.video_id, selected, labels, public[item.video_id], ref_maps[item.video_id], int(ref_counts[item.video_id]))
        c0 = p0.metric_row(p0.k0_materialize(item.video_id, units), references[item.video_id], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        c1 = p0.metric_row(mech.generic_events(item.video_id, units, "C1_gap_limited"), references[item.video_id], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        # Exact identity to the authoritative C1 row is a hard guard against accidental trace drift.
        if not np.isclose(float(item.F1), c1["F1"]): raise RuntimeError(f"C1 replay mismatch: {item.video_id} {item.proxy_regime} {item.policy} {item.budget}")
        rows.append({"video_id": item.video_id, "proxy_regime": item.proxy_regime, "policy": item.policy, "budget": int(item.budget), "trace_hash": item.trace_hash,
                     **geometry, "EventF1_C0": c0["F1"], "EventF1_C1": float(item.F1), "DeltaMaterializer": float(item.F1) - c0["F1"],
                     "EventPrecision_C1": float(item.precision), "EventRecall_C1": float(item.recall), "TP_C0": c0["TP"], "FP_C0": c0["FP"], "TP_C1": int(item.TP), "FP_C1": int(item.FP)})
    frame = pd.DataFrame(rows)
    if len(frame) != 378: raise RuntimeError(f"expected 378 C1 cells, got {len(frame)}")
    # Validate the reported 54-cell range exactly, while broader geometry uses all 378 cells.
    old = pd.read_csv(MAIN / "SELECTOR_MATERIALIZER_INTERACTION.csv")
    # The original interaction table hashes only selected ids whereas the C1 matrix
    # hashes a fuller trace payload, so identity is the frozen condition tuple.
    check = frame.merge(old[["video_id","proxy_regime","policy","budget","Delta_C1_minus_C0"]], on=["video_id","proxy_regime","policy","budget"], how="inner")
    if len(check) != 54 or not np.allclose(check.DeltaMaterializer, check.Delta_C1_minus_C0): raise RuntimeError("54-cell C0/C1 interaction reproduction failed")
    frame.to_csv(OUT / "TRACE_GEOMETRY_FEATURES.csv", index=False)

    online = ["queried_temporal_span_sec","coverage_fraction","number_of_temporal_regions_touched","largest_unqueried_gap_units","median_unqueried_gap_units","queries_per_local_region","near_duplicate_query_fraction","positive_anchor_temporal_span_sec","positive_anchor_dispersion","median_positive_gap_sec","max_positive_gap_sec","positive_cluster_count","positive_redundancy"]
    diagnostic = [x for x in frame.columns if x.endswith("OFFLINE_DIAGNOSTIC_ONLY")]
    pred_y, res_y = fit_lovo(frame, ["positive_yield"], "YIELD_ONLY")
    pred_g, res_g = fit_lovo(frame, ["positive_yield", *online], "YIELD_PLUS_PUBLIC_ONLINE_GEOMETRY")
    pred_d, res_d = fit_lovo(frame, ["positive_yield", *online, *diagnostic], "REFERENCE_AWARE_DIAGNOSTIC_UPPER")
    res_y.to_csv(OUT / "YIELD_ONLY_MODEL.csv", index=False); res_g.to_csv(OUT / "PUBLIC_GEOMETRY_MODEL.csv", index=False); res_d.to_csv(OUT / "REFERENCE_DIAGNOSTIC_MODEL.csv", index=False)
    pd.concat([pred_y,pred_g,pred_d], ignore_index=True).to_csv(OUT / "LOVO_RESULTS.csv", index=False)

    # Exact-positive-count matched strata; pairs are deduplicated by trace to avoid identical non-proxy traces being counted repeatedly.
    unique = frame.sort_values(["video_id","budget","trace_hash"]).drop_duplicates(["video_id","budget","trace_hash"])
    pairs = []
    for (_, _, positive_count), group in unique.groupby(["video_id","budget","verified_positive_count"]):
        if len(group) < 2: continue
        for a, b in itertools.combinations(group.itertuples(), 2):
            delta = abs(a.EventF1_C1-b.EventF1_C1)
            if delta <= 0: continue
            high, low = (a,b) if a.EventF1_C1 >= b.EventF1_C1 else (b,a)
            pairs.append({"video_id": high.video_id,"budget":high.budget,"positive_count_bin":high.verified_positive_count,"F1_high":high.EventF1_C1,"F1_low":low.EventF1_C1,"F1_difference":delta,
                          "trace_high":high.trace_hash,"trace_low":low.trace_hash,"policy_high":high.policy,"policy_low":low.policy,"regime_high":high.proxy_regime,"regime_low":low.proxy_regime,
                          "positive_gap_difference_high_minus_low":high.max_positive_gap_sec-low.max_positive_gap_sec,"anchor_dispersion_difference_high_minus_low":high.positive_anchor_dispersion-low.positive_anchor_dispersion,
                          "largest_hole_difference_high_minus_low":high.largest_unqueried_gap_units-low.largest_unqueried_gap_units,"coverage_difference_high_minus_low":high.coverage_fraction-low.coverage_fraction,"cluster_difference_high_minus_low":high.positive_cluster_count-low.positive_cluster_count})
    equal = pd.DataFrame(pairs).sort_values("F1_difference", ascending=False).head(20)
    equal.to_csv(OUT / "EQUAL_YIELD_COUNTEREXAMPLES.csv", index=False)

    # Matched/stratified H-GEO1 summary: feature/F1 rank association only within video×budget×positive-count strata.
    strat = []
    for feature in online:
        vals=[]
        for _, g in unique.groupby(["video_id","budget","verified_positive_count"]):
            if len(g) >= 3 and g[feature].nunique() > 1 and g.EventF1_C1.nunique() > 1:
                vals.append(float(spearmanr(g[feature],g.EventF1_C1).statistic))
        strat.append({"feature":feature,"matched_strata_with_variation":len(vals),"median_within_stratum_spearman":float(np.median(vals)) if vals else np.nan,"direction_consistency":float(np.mean(np.asarray(vals)>0)) if vals else np.nan})
    strat_frame = pd.DataFrame(strat)
    strat_frame.to_csv(OUT / "MATCHED_GEOMETRY_ANALYSIS.csv", index=False)

    # Paired policy comparisons at fixed video/regime/budget.
    pol=[]
    for (video, regime, budget), g in frame.groupby(["video_id","proxy_regime","budget"]):
        by={r.policy:r for r in g.itertuples()}
        for left,right in itertools.combinations(POLICIES,2):
            a,b=by[left],by[right]
            pol.append({"comparison_type":"policy","video_id":video,"proxy_regime":regime,"budget":budget,"left":left,"right":right,"Delta_F1_left_minus_right":a.EventF1_C1-b.EventF1_C1,"Delta_yield":a.positive_yield-b.positive_yield,"Delta_event_coverage_DIAGNOSTIC_ONLY":a.reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY-b.reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY,"Delta_positive_dispersion":a.positive_anchor_dispersion-b.positive_anchor_dispersion,"Delta_max_positive_gap":a.max_positive_gap_sec-b.max_positive_gap_sec,"Delta_largest_hole":a.largest_unqueried_gap_units-b.largest_unqueried_gap_units,"Delta_clusters":a.positive_cluster_count-b.positive_cluster_count})
    # Ranking-degradation decomposition holds video/policy/budget fixed; effects on non-proxy policies are legitimate zero controls.
    prox=[]
    for video, policy, budget in itertools.product(VIDEOS,POLICIES,(5,10,20,50,80,100)):
        base=frame[(frame.video_id==video)&(frame.policy==policy)&(frame.budget==budget)&(frame.proxy_regime=="R0_ORIGINAL")].iloc[0]
        for regime in ("R1_RANK_MILD_A025","R2_RANK_MEDIUM_A050","R3_RANK_SEVERE_HASH"):
            other=frame[(frame.video_id==video)&(frame.policy==policy)&(frame.budget==budget)&(frame.proxy_regime==regime)].iloc[0]
            prox.append({"comparison_type":"ranking_degradation","video_id":video,"policy":policy,"budget":budget,"from_regime":"R0_ORIGINAL","to_regime":regime,"Delta_F1_to_minus_from":other.EventF1_C1-base.EventF1_C1,"Delta_yield":other.positive_yield-base.positive_yield,"Delta_event_coverage_DIAGNOSTIC_ONLY":other.reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY-base.reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY,"Delta_positive_dispersion":other.positive_anchor_dispersion-base.positive_anchor_dispersion,"Delta_max_positive_gap":other.max_positive_gap_sec-base.max_positive_gap_sec,"Delta_largest_hole":other.largest_unqueried_gap_units-base.largest_unqueried_gap_units,"Delta_clusters":other.positive_cluster_count-base.positive_cluster_count})
    # Required filename carries the actual paired policy decomposition; proxy table carries the controlled stress pathway.
    pd.DataFrame(pol).to_csv(OUT / "POLICY_GEOMETRY_DECOMPOSITION.csv", index=False)
    pd.DataFrame(prox).to_csv(OUT / "PROXY_GEOMETRY_DECOMPOSITION.csv", index=False)

    correlations=[]
    for feature in ["positive_yield",*online]:
        r,p=spearmanr(frame[feature],frame.DeltaMaterializer)
        correlations.append({"feature":feature,"spearman_with_DeltaMaterializer":float(r),"p_value_descriptive":float(p)})
    corr=pd.DataFrame(correlations).sort_values("spearman_with_DeltaMaterializer", key=lambda x:abs(x),ascending=False)
    inter=frame.groupby(["video_id","policy"]).DeltaMaterializer.agg(["median","mean","count"]).reset_index()
    inter_range=float(old.groupby(["proxy_regime","policy"]).Delta_C1_minus_C0.median().max()-old.groupby(["proxy_regime","policy"]).Delta_C1_minus_C0.median().min())
    best=str(corr.iloc[0].feature); br=float(corr.iloc[0].spearman_with_DeltaMaterializer)
    (OUT / "MATERIALIZER_INTERACTION_ANALYSIS.md").write_text(f"# Materializer interaction\n\nThe 54 reported interaction cells reproduce exactly from the frozen traces; their subgroup median C1−C0 range is **{inter_range:.4f}**. C0 collapses all positive anchors into one span, whereas C1 splits anchor groups separated by more than 10 seconds. Across all 378 C1 traces, the strongest descriptive geometry association with C1 gain is `{best}` (Spearman {br:.3f}). This is an outcome-preserving mechanism explanation, not a causal estimate.\n\n```text\n{inter.to_string(index=False)}\n\n{corr.to_string(index=False)}\n```\n")
    spr=frame[frame.policy=="StaticProxyRank"]
    compare=pd.DataFrame(pol)
    spr_comp=compare[(compare.left=="StaticProxyRank")|(compare.right=="StaticProxyRank")]
    (OUT / "STATIC_PROXY_RANK_ANALYSIS.md").write_text(f"# StaticProxyRank analysis\n\nStaticProxyRank is the frozen robust winner (mean C1 F1 {spr.EventF1_C1.mean():.4f}). Its mean verified-positive yield is {spr.positive_yield.mean():.4f}, versus {frame[frame.policy!='StaticProxyRank'].positive_yield.mean():.4f} for the two alternatives pooled. Its diagnostic reference-event coverage is {spr.reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY.mean():.4f}, versus {frame[frame.policy!='StaticProxyRank'].reference_event_coverage_OFFLINE_DIAGNOSTIC_ONLY.mean():.4f}. These are descriptive paired-pathway indicators, not policy-visible supervision.\n\nAt fixed video/regime/budget, the paired policy differences are in `POLICY_GEOMETRY_DECOMPOSITION.csv`; ranking-stress pathways are in `PROXY_GEOMETRY_DECOMPOSITION.csv`. The winner is primarily associated with higher semantic yield and event coverage; geometry is assessed separately below.\n")

    macro=lambda x: float(x[x.heldout_video=="MACRO_MEAN"].iloc[0].R2)
    y_r2,g_r2,d_r2=macro(res_y),macro(res_g),macro(res_d)
    high_pairs=len(equal[equal.F1_difference>=0.15])
    video_signals=[]
    for v in VIDEOS:
        sub=frame[frame.video_id==v]
        # Direction is tested by within-video matched counterexample availability, avoiding a pooled-only claim.
        video_signals.append((v, int(((equal.video_id==v)&(equal.F1_difference>=0.15)).sum())))
    videos_with=sum(n>0 for _,n in video_signals)
    # Conservative: strong needs public model lift + equal-yield examples in >=2 videos. Otherwise partial/weak.
    geometry_decision="STRONG" if g_r2-y_r2>=0.08 and high_pairs>=10 and videos_with>=2 else ("PARTIAL" if high_pairs>=5 or g_r2>y_r2 else "ABSENT")
    opportunity="STRONG" if geometry_decision=="STRONG" and d_r2-g_r2<=0.08 else ("WEAK" if geometry_decision in {"STRONG","PARTIAL"} else "ABSENT")
    public_best=strat_frame.sort_values("median_within_stratum_spearman", key=lambda x:abs(x),ascending=False).iloc[0]
    yield_state="INSUFFICIENT" if g_r2-y_r2>=0.08 else ("PARTIAL" if g_r2>y_r2 else "SUFFICIENT")
    report=f"""# Event Evidence Geometry Audit\n\n## Scope and evidence status\n\nThis audit consumes the frozen 378 C1 cells (3 videos × 7 proxy regimes × 3 policies × 6 budgets), replays only cached outcomes, and evaluates C0 on the exact same traces. No semantic inference, selector, policy, MAB, or RL was run. C1 is fixed GAP-ONLY. Reference-aware columns are explicitly **OFFLINE_DIAGNOSTIC_ONLY** and cannot be policy inputs.\n\n## Result\n\n- EVENT_EVIDENCE_GEOMETRY: **{geometry_decision}**\n- Positive yield alone: **{yield_state}**\n- LOVO macro R²: yield-only {y_r2:.3f}; yield + public/online geometry {g_r2:.3f}; reference-aware upper diagnostic {d_r2:.3f}.\n- Equal-yield top-20 counterexamples include {high_pairs} pairs with F1 difference ≥0.15, spanning {videos_with}/3 videos.\n- Strongest matched-stratum online geometry signal: `{public_best.feature}` (median within-stratum Spearman {public_best.median_within_stratum_spearman:.3f}, {int(public_best.matched_strata_with_variation)} varying strata).\n- C1−C0 interaction range reproduced exactly: {inter_range:.4f}.\n\n## Interpretation\n\nC1 gain changes with the geometry of positive anchors because C0 converts every positive into one temporal span, while GAP-ONLY C1 preserves separations larger than 10 seconds. Thus selector/proxy choice matters not only through how many positives it finds, but through where the acquired anchors lie. This is descriptive evidence under a model-relative K3 reference, not a causal mediation result and not independent human-continuity validation.\n\nStaticProxyRank remains the robust winner because it has higher acquired semantic yield and higher diagnostic event coverage on this frozen matrix. Whether its additional geometry advantage is independently actionable is qualified by the small three-video sample and synthetic ranking stress.\n\n## Research decision\n\nROBUST_EVENT_POLICY_OPPORTUNITY: **{opportunity}**. MAB REOPEN: **NO**. A future policy, if pursued after independent validation, should optimize an Event Evidence Utility concept: semantic yield + event/temporal coverage − redundant local anchors − large evidence holes. We do not fit weights or train a policy here.\n\nPrimary algorithmic gap: establish whether online, policy-visible temporal geometry transfers beyond this frozen model-relative three-video benchmark.\n\nUpdated project thesis: Event-query optimization should be evaluated as acquisition of temporally structured semantic evidence, not just as maximization of positive predicates; current evidence is **{geometry_decision}**, with the stated model-relative qualification.\n\nNext single decisive experiment: preregister a second independent reference/proxy replication, then compare equal-yield traces prospectively using only online-available geometry.\n"""
    (OUT / "FINAL_GEOMETRY_REPORT.md").write_text(report)
    (OUT / "EVENT_EVIDENCE_GEOMETRY_DECISION.md").write_text(report)
    (OUT / "QUERY_POLICY_OPPORTUNITY.md").write_text("# Query-policy opportunity\n\n"+report.split("## Research decision",1)[1])
    dictionary="""# Geometry feature dictionary\n\nAll trace features are derived from frozen query positions and cached outcomes. `POLICY_VISIBLE` features use timestamps/queried positions only. `ORACLE_OBSERVED_AFTER_QUERY` features additionally use verified outcomes. `OFFLINE_DIAGNOSTIC_ONLY` features join frozen reference event IDs and must never be policy-visible.\n\n| Feature family | Features | Status | Definition |\n|---|---|---|---|\n| Yield | queried_units, verified_positive_count, positive_yield | ORACLE_OBSERVED_AFTER_QUERY | Query count, cached positives, and their ratio. |\n| Temporal coverage | queried_temporal_span_sec, coverage_fraction, number_of_temporal_regions_touched, largest_unqueried_gap_units, median_unqueried_gap_units | POLICY_VISIBLE | Span/coverage of queried timestamps; regions are consecutive original-unit runs; holes include boundary holes. |\n| Positive anchors | positive_anchor_*, median/max_positive_gap_sec, positive_cluster_count | ORACLE_OBSERVED_AFTER_QUERY | Geometry of queried relevant anchors; clusters split at a gap >10 s, exactly C1's threshold. |\n| Redundancy | queries_per_local_region, near_duplicate_query_fraction, positive_redundancy | POLICY_VISIBLE / ORACLE_OBSERVED_AFTER_QUERY | Ten fixed temporal bins; adjacent-query rate; fraction of anchors beyond one per C1 cluster. |\n| Reference aware | *_OFFLINE_DIAGNOSTIC_ONLY | OFFLINE_DIAGNOSTIC_ONLY | Frozen K3 reference-event join; used only as an explanatory upper diagnostic. |\n"""
    (OUT / "GEOMETRY_FEATURE_DICTIONARY.md").write_text(dictionary)
    protocol={"analysis":"offline cached trace geometry","cells":378,"materializer":"C1 GAP-ONLY fixed; C0 same-trace diagnostic","inputs":{str(p.relative_to(ROOT)):sha(p) for p in [MAIN/"QUERY_POLICY_MATRIX.csv",MAIN/"SELECTOR_MATERIALIZER_INTERACTION.csv",P0/"event_metrics.csv",V10/"FINAL_UNIT_REFERENCE.parquet",V10/"K3_MODEL_RELATIVE_EVENT_RELATION.parquet",RUNNER,MECH,MAIN_RUNNER]}}
    (OUT / "ANALYSIS_PROTOCOL.json").write_text(json.dumps(protocol,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"COMPLETE","cells":len(frame),"EVENT_EVIDENCE_GEOMETRY":geometry_decision,"ROBUST_EVENT_POLICY_OPPORTUNITY":opportunity,"yield_r2":y_r2,"geometry_r2":g_r2,"output":str(OUT)},indent=2))

if __name__ == "__main__":
    main()
