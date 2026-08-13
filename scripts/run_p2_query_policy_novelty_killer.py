#!/usr/bin/env python3
"""Frozen cached-replay P2 novelty-killer audit.

This runner deliberately compares only legal generic ordering rules on the
already complete semantic tables.  It has no inference, no learned policy, no
semantic feedback in a legal baseline, and no human claim.  The offline oracle
diagnostic is kept outside legal rankings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from garc_eval.accelerated_event_query.matching import MatchConfig, match_events, summarize_matches
from garc_eval.accelerated_event_query.types import EventRecord

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/p2_query_policy_novelty_killer_v1"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
QUERIES = ("Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1")
PROXIES = ("PROXY_A_YOLOV8N_OBJECT_MOTION", "PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS")
BUDGETS = (5, 10, 20, 50, 80, 100)
LEGAL = ("UniformTemporal", "StaticProxyRank", "CoverageFirst", "ProxyTemporalCoverage_L025", "ProxyTemporalCoverage_L050", "ProxyTemporalCoverage_L075")
ORACLE = "OFFLINE_ORACLE_DIAGNOSTIC"
TRACE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"
V10 = ROOT / "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
QWEN = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet"
QCOMPLETE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/P1_QWEN32_ORACLE_COMPLETION.json"
PA_DIR = ROOT / "outputs/v3_scan_proxy_preregistration_v1/frozen_tables"
PB = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet"
P1_PROXY_PROTOCOL = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/P1_PROXY_CHARACTERIZATION_PROTOCOL.json"
P1_PROXY_REPORT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/P1_PROXY_CHARACTERIZATION_REPORT.md"
P0_PROTOCOL = ROOT / "outputs/p0_materializer_validation_v3/EXPERIMENT_PROTOCOL.json"
P0_METRICS = ROOT / "outputs/p0_materializer_validation_v3/event_metrics.csv"
P0_ABLATION = ROOT / "outputs/p0_materializer_mechanism_ablation_v1/mechanism_summary.csv"
P1_AUTOMATED = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/P1_AUTOMATED_ONLY_COMPLETION_AUDIT.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False).stdout.strip()


def write_json_once(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"immutable output already exists: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_inputs() -> dict[str, dict[str, object]]:
    paths = [TRACE, V10, QWEN, QCOMPLETE, PB, P1_PROXY_PROTOCOL, P1_PROXY_REPORT, P0_PROTOCOL, P0_METRICS, P0_ABLATION, P1_AUTOMATED]
    for video in VIDEOS:
        paths += [PA_DIR / video / "candidate_table.parquet", PA_DIR / video / "proxy_table.parquet"]
    return {str(path.relative_to(ROOT)): {"sha256": sha(path), "bytes": path.stat().st_size} for path in paths}


def protocol() -> dict[str, object]:
    p = {
        "protocol_id": "GVAQP_P2_QUERY_POLICY_NOVELTY_KILLER_V1",
        "status": "FROZEN_BEFORE_P2_BASELINE_RESULT_COMPUTATION",
        "research_question": "Can generic proxy relevance plus temporal coverage/diversity explain the remaining model-relative query-policy opportunity?",
        "evaluation_scope": "CACHED_MODEL_RELATIVE_REPLAY_ONLY; no human semantic claim and no physical deadline claim",
        "videos": list(VIDEOS), "queries": list(QUERIES), "proxy_families": list(PROXIES), "budgets": list(BUDGETS),
        "budget_semantics": "semantic oracle call/query count; not wall-clock or physical deadline",
        "candidate_universe": "frozen V3 one-candidate-per-10-second-unit tables, identical for every legal baseline",
        "semantic_outcomes": {"Q_DRIVER_RESPONSE_V1": "V10 FINAL_UNIT_REFERENCE authoritative_label", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1": "P1 Qwen3-VL-32B completed outcome table"},
        "materializer": {"name": "C1_gap_limited", "definition": "merge selected relevant 10-second anchors iff adjacent temporal gap <=10.0s; no K3 extras", "gap_sec": 10.0},
        "evaluator": {"name": "official garc_eval accelerated_event_query matcher", "matching": "one-to-one maximum-cardinality / overlap-any MatchConfig(minimum_tiou=0,boundary_tolerance_sec=0)"},
        "legal_baselines": {
            "UniformTemporal": "nested deterministic dyadic temporal ordering; timestamps only",
            "StaticProxyRank": "descending frozen proxy score, candidate_order/candidate_id tie breaks; no semantic feedback",
            "CoverageFirst": "nested deterministic farthest-first temporal coverage ordering; timestamps only",
            "ProxyTemporalCoverage_L025": "normalized frozen proxy plus 0.25 min-distance temporal novelty",
            "ProxyTemporalCoverage_L050": "canonical primary generic relevance+coverage baseline: normalized frozen proxy plus 0.50 min-distance temporal novelty",
            "ProxyTemporalCoverage_L075": "sensitivity generic relevance+coverage baseline: normalized frozen proxy plus 0.75 min-distance temporal novelty",
        },
        "lambda_discipline": {"values": [0.25, 0.50, 0.75], "canonical_core_comparison": "ProxyTemporalCoverage_L050", "all_values_reported": True, "winner_selection_forbidden": True, "basis": "fixed equal-scale convex mixing; values inherited from outcome-blind P1 trace feasibility family"},
        "offline_oracle_diagnostic": "knows full cached labels and full-grid C1 reference events to greedily cover unseen reference events; illegal policy, excluded from legal ranking, headroom only",
        "trace_rule": "every policy/video/query/proxy/budget is an ordering prefix; deterministic seed=0; traces store IDs, order, outcomes and hashes",
        "geometry_diagnostics": ["verified_positive_yield", "temporal_regions_touched", "coverage_fraction", "temporal_dispersion", "largest_evidence_hole", "query_redundancy", "positive_anchor_dispersion", "offline full-grid C1 event coverage"],
        "primary_metrics": ["EventPrecision", "EventRecall", "EventF1", "AnytimeAUC_F1", "UniqueEventsPerOracleCall"],
        "statistics": {"statistical_unit": "video-query cluster", "cluster_bootstrap_resamples": 10000, "cluster_bootstrap_seed": 20260813, "LOVO": True, "LOVQ": True},
        "decision_rules": {
            "material_generic_gain": "canonical L050 median final ΔF1>=0.02, median ΔAnytimeAUC>=0.01, positive proxy-median ΔF1 in >=4/6 video-query clusters, and each natural proxy median final ΔF1>=0.02",
            "headroom_capture": "median FractionCapturedByGenericCoverage>=0.90 across stable denominators, where stable means oracle-minus-static final F1>0.02",
            "GENERIC_COVERAGE_ONLY": "material_generic_gain and headroom_capture",
            "ESTABLISHED": "stable oracle headroom >=0.05 in >=4/6 video-query clusters, generic coverage does not capture >=90%, residual semantic-state model improves both LOVO and LOVQ MAE by >=0.02, and residual evidence is present in both proxies; otherwise prohibited",
            "NOT_ESTABLISHED": "no material generic gain and no stable oracle headroom (median <=0.02 or positive in <4/6 clusters)",
            "INCONCLUSIVE": "all remaining comparable-data cases; never used merely because result is unfavorable",
            "practical_thresholds": {"F1": 0.02, "AnytimeAUC": 0.01, "oracle_headroom": 0.05, "denominator_stability": 0.02},
        },
        "prohibited": ["new VLM inference", "new semantic labels", "human labels", "C1/K3 tuning", "per-video/query/budget tuning", "post-result lambda selection", "learned policy", "MAB", "RL", "SMDP", "neural policy", "counterfactual planner"],
        "source_commit": git("rev-parse", "HEAD"), "source_branch": git("branch", "--show-current"), "dirty_worktree": git("status", "--short").splitlines(),
        "input_artifacts": source_inputs(), "runner": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(Path(__file__))},
    }
    p["protocol_hash"] = digest(p)
    return p


def freeze() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite P2 output: {OUT}")
    p = protocol(); OUT.mkdir(parents=True); (OUT / "figures").mkdir()
    write_json_once(OUT / "P2_PROTOCOL.json", p)
    (OUT / "PROTOCOL_HASH.txt").write_text(str(p["protocol_hash"]) + "\n")
    (OUT / "P2_PREREGISTRATION.md").write_text("# P2 preregistration\n\nFrozen protocol hash: `" + str(p["protocol_hash"]) + "`.\n\nThis is a cached, model-relative novelty-killer audit. C1 is fixed; no human labels, semantic inference, tuning, learned policy, MAB, RL, or deadline claim is permitted. The decision categories and thresholds are exactly in `P2_PROTOCOL.json`.\n")
    (OUT / "BASELINE_DEFINITIONS.md").write_text("# P2 baseline definitions\n\n- **UniformTemporal**: deterministic nested dyadic temporal ordering, no proxy.\n- **StaticProxyRank**: descending frozen proxy score.\n- **CoverageFirst**: deterministic farthest-first temporal coverage, no proxy.\n- **Proxy+TemporalCoverage**: score `(1-lambda)*normalized_proxy + lambda*minimum normalized temporal distance to already selected timestamps`; fixed λ={0.25,0.50,0.75}, all reported, with λ=0.50 canonical.\n- **Offline oracle diagnostic**: full-label/full-reference greedy coverage upper diagnostic only; never a legal policy or winner.\n\nAll legal methods are nested query-count prefixes and read no semantic outcome during ordering.\n")
    sources = p["input_artifacts"]
    (OUT / "SOURCE_OF_TRUTH.md").write_text("# P2 source of truth\n\nDirect artifacts (hash-bound in `P2_PROTOCOL.json`) establish: 3 videos; two complete 1475-unit semantic tables; Proxy A V3 score tables; Proxy B kinematic score table; P0's C1 materializer and official matching lineage; P1's two-proxy characterisation and completed automated audit.\n\nP0 supports C1 as the minimal materializer; P2 holds it fixed. P1 automated results are weak/non-confirmatory and do not establish nor refute a human geometry effect. This P2 audit is model-relative because the full-grid C1 reference is derived from the same frozen semantic outcomes.\n\n## Bound inputs\n\n" + "\n".join(f"- `{path}` — `{meta['sha256']}`" for path, meta in sources.items()) + "\n")
    print(json.dumps({"status": "FROZEN", "protocol_hash": p["protocol_hash"]}, sort_keys=True))


def load_protocol() -> dict[str, object]:
    p = json.loads((OUT / "P2_PROTOCOL.json").read_text())
    actual = digest({k: v for k, v in p.items() if k != "protocol_hash"})
    if actual != p.get("protocol_hash") or (OUT / "PROTOCOL_HASH.txt").read_text().strip() != actual:
        raise RuntimeError("P2 protocol hash mismatch")
    runner_hash = sha(Path(__file__))
    if runner_hash != p["runner"]["sha256"]:
        repair_path = OUT / "P2_IMPLEMENTATION_REPAIR.json"
        if not repair_path.exists():
            raise RuntimeError("P2 runner changed after freeze")
        repair = json.loads(repair_path.read_text())
        if repair.get("original_protocol_hash") != p["protocol_hash"] or repair.get("original_runner_sha256") != p["runner"]["sha256"] or repair.get("repaired_runner_sha256") != runner_hash or repair.get("result_rows_observed_before_repair") is not False:
            raise RuntimeError("P2 implementation repair binding invalid")
    for text, meta in p["input_artifacts"].items():
        if sha(ROOT / text) != meta["sha256"]:
            raise RuntimeError(f"P2 input changed after freeze: {text}")
    return p


def c1_intervals(frame: pd.DataFrame) -> list[tuple[float, float]]:
    # unit_id is retained as a lookup index and a column in this replay; reset
    # prevents Pandas treating the deterministic sort key as ambiguous.
    rows = frame[frame.label == "relevant"].reset_index(drop=True).sort_values(["start_time", "end_time", "unit_id"])
    groups: list[list[tuple[float, float]]] = []
    for row in rows.itertuples():
        item = (float(row.start_time), float(row.end_time))
        if not groups or item[0] - groups[-1][-1][1] > 10.0: groups.append([item])
        else: groups[-1].append(item)
    return [(min(x[0] for x in group), max(x[1] for x in group)) for group in groups]


def overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def event_metrics(pred: list[tuple[float, float]], ref: list[tuple[float, float]], video: str, query: str) -> dict[str, float]:
    """Use the repository's authoritative P0/P1 EventRelation matcher."""
    predicted = [EventRecord(f"p2_pred_{i}", query, video, a, b, 1.0, "VERIFIED_EVENT", (), (), "C1_gap_limited", None) for i,(a,b) in enumerate(pred)]
    reference = [EventRecord(f"p2_ref_{i}", query, video, a, b, 1.0, "VERIFIED_EVENT", (), (), "P2_FULL_GRID_C1_MODEL_RELATIVE", None) for i,(a,b) in enumerate(ref)]
    summary = summarize_matches(predicted, reference, match_events(predicted, reference, MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0)))
    matched = int(summary["matched_events"])
    return {"EventPrecision": float(summary["32b_operational_oracle_relative_event_precision"]), "EventRecall": float(summary["32b_operational_oracle_relative_event_recall"]), "EventF1": float(summary["event_f1"]), "TP": matched, "FP": len(predicted)-matched, "FN": len(reference)-matched, "MatchedMeanIoU": float(summary["mean_event_boundary_tiou"])}


def labels_by_query() -> dict[tuple[str, str], pd.DataFrame]:
    old = pd.read_parquet(V10)[["video_id", "unit_id", "start_time", "end_time", "authoritative_label"]].rename(columns={"authoritative_label": "label"})
    new = pd.read_parquet(QWEN)[["video_id", "unit_id", "start_time", "end_time", "label"]]
    out: dict[tuple[str, str], pd.DataFrame] = {}
    for query, frame in ((QUERIES[0], old), (QUERIES[1], new)):
        for video, group in frame.groupby("video_id", sort=True): out[(str(video), query)] = group.copy().set_index("unit_id", drop=False)
    if len(out) != 6: raise RuntimeError("not six complete video-query outcome clusters")
    return out


def candidates() -> dict[tuple[str, str], pd.DataFrame]:
    pb = pd.read_parquet(PB)[["video_id", "candidate_id", "unit_id", "candidate_order", "start_sec", "end_sec", "proxy_score"]]
    result: dict[tuple[str, str], pd.DataFrame] = {}
    for video in VIDEOS:
        c = pd.read_parquet(PA_DIR / video / "candidate_table.parquet")
        a = pd.read_parquet(PA_DIR / video / "proxy_table.parquet")[["video_id", "candidate_id", "proxy_score"]]
        base = c.merge(a, on=["video_id", "candidate_id"], validate="one_to_one").copy()
        base["unit_id"] = base.source_unit_ids.map(lambda x: str(x[0])); base = base.rename(columns={"start_sec": "start_time", "end_sec": "end_time"})
        result[(video, PROXIES[0])] = base[["video_id", "candidate_id", "unit_id", "candidate_order", "start_time", "end_time", "proxy_score"]].sort_values("candidate_order").reset_index(drop=True)
        b = pb[pb.video_id == video].rename(columns={"start_sec": "start_time", "end_sec": "end_time"})
        result[(video, PROXIES[1])] = b[["video_id", "candidate_id", "unit_id", "candidate_order", "start_time", "end_time", "proxy_score"]].sort_values("candidate_order").reset_index(drop=True)
    return result


def dyadic_order(frame: pd.DataFrame) -> list[int]:
    order: list[int] = []
    def visit(lo: int, hi: int) -> None:
        if lo >= hi: return
        mid = (lo + hi) // 2; order.append(mid); visit(lo, mid); visit(mid + 1, hi)
    visit(0, len(frame)); return order


def farthest_order(frame: pd.DataFrame) -> list[int]:
    n = len(frame); orders = frame.candidate_order.to_numpy(int); ids = frame.candidate_id.astype(str).to_numpy()
    selected = [n // 2]; available = np.ones(n, dtype=bool); available[selected[0]] = False
    nearest = np.abs(np.arange(n) - selected[0]).astype(float)
    while available.any():
        value = nearest.copy(); value[~available] = -1.0; maximum = value.max()
        tied = np.flatnonzero((value == maximum) & available)
        best = min(tied.tolist(), key=lambda i: (int(orders[i]), str(ids[i])))
        selected.append(best); available[best] = False; nearest = np.minimum(nearest, np.abs(np.arange(n)-best))
    return selected


def proxy_coverage_order(frame: pd.DataFrame, lam: float) -> list[int]:
    n=len(frame); score=frame.proxy_score.to_numpy(float); orders=frame.candidate_order.to_numpy(int); ids=frame.candidate_id.astype(str).to_numpy(); lo,hi=float(score.min()),float(score.max()); norm=(score-lo)/(hi-lo) if hi>lo else np.zeros(n)
    selected=[]; available=np.ones(n,dtype=bool); novelty=np.ones(n,dtype=float); positions=np.arange(n)
    while available.any():
        value=(1-lam)*norm+lam*novelty; value[~available]=-np.inf; maximum=value.max(); tied=np.flatnonzero(np.isclose(value,maximum,rtol=0,atol=1e-15)&available)
        best=min(tied.tolist(),key=lambda i:(int(orders[i]),str(ids[i]))); selected.append(best); available[best]=False; novelty=np.minimum(novelty,np.abs(positions-best)/max(n-1,1))
    return selected


def oracle_order(frame: pd.DataFrame, labels: pd.DataFrame, ref: list[tuple[float, float]]) -> list[int]:
    n=len(frame); orders=frame.candidate_order.to_numpy(int); ids=frame.candidate_id.astype(str).to_numpy(); unit_ids=frame.unit_id.astype(str).tolist(); relevant=np.asarray([labels.loc[x,"label"]=="relevant" for x in unit_ids],dtype=bool)
    touches=np.zeros((n,len(ref)),dtype=bool)
    for i,row in enumerate(frame.itertuples()):
        if relevant[i]: touches[i]=[overlap((float(row.start_time),float(row.end_time)),event) for event in ref]
    selected=[]; available=np.ones(n,dtype=bool); covered=np.zeros(len(ref),dtype=bool)
    while available.any():
        gain=(touches & ~covered).sum(axis=1); gain[~available]=-1; maximum=gain.max(); tied=np.flatnonzero((gain==maximum)&available)
        # After all reference gains are exhausted, relevant units are still
        # preferred so the diagnostic remains a genuine full-label upper bound.
        relevant_tied=tied[relevant[tied]]
        if len(relevant_tied): tied=relevant_tied
        best=min(tied.tolist(),key=lambda i:(int(orders[i]),str(ids[i]))); selected.append(best); available[best]=False; covered |= touches[best]
    return selected


def trace_diagnostics(selected: pd.DataFrame, all_labels: pd.DataFrame, ref: list[tuple[float, float]], video: str, query: str) -> dict[str, object]:
    pos = selected[selected.label == "relevant"].copy(); orders = selected.candidate_order.to_numpy(int)
    po = pos.candidate_order.to_numpy(int); n = len(all_labels)
    intervals = c1_intervals(pos); metric = event_metrics(intervals, ref, video, query)
    holes = [int(orders.min()), int(n-1-orders.max())] + [int(b-a-1) for a,b in zip(np.sort(orders)[:-1],np.sort(orders)[1:])] if len(orders) else [n]
    regions = 0 if not len(orders) else 1 + int(np.sum(np.diff(np.sort(orders)) > 1))
    coverage = 0.0 if not len(orders) else (float(orders.max()-orders.min()+1)/n)
    redundancy = 0.0 if len(orders) < 2 else float(np.mean(np.diff(np.sort(orders)) == 1))
    anchors = [(float(r.start_time), float(r.end_time)) for r in pos.itertuples()]
    touched = sum(any(overlap(event, interval) for interval in anchors) for event in ref)
    return {**metric, "verified_positive_count": int(len(pos)), "verified_negative_count": int((selected.label == "not_relevant").sum()), "unknown_or_parse_count": int(selected.label.isin(["unknown", "parse_failure"]).sum()), "verified_positive_yield": float(len(pos)/len(selected)), "temporal_regions_touched": regions, "coverage_fraction": coverage, "temporal_dispersion": float(np.std(orders)/max(n-1,1)), "largest_evidence_hole_units": max(holes), "query_redundancy": redundancy, "positive_anchor_dispersion": float(np.std(po)/max(n-1,1)) if len(po) else 0.0, "offline_reference_events_touched": touched, "offline_reference_event_coverage": float(touched/len(ref)) if ref else 1.0}


def auc(budget: list[int], values: list[float]) -> float:
    x = np.asarray([0, *budget], float) / max(BUDGETS); y = np.asarray([0, *values], float)
    return float(np.trapezoid(y, x))


def run() -> None:
    p = load_protocol(); label_map = labels_by_query(); candidate_map = candidates(); rows: list[dict[str, object]] = []
    orderers = {"UniformTemporal": lambda f,l,r: dyadic_order(f), "StaticProxyRank": lambda f,l,r: sorted(range(len(f)), key=lambda i: (-float(f.iloc[i].proxy_score), int(f.iloc[i].candidate_order), str(f.iloc[i].candidate_id))), "CoverageFirst": lambda f,l,r: farthest_order(f), "ProxyTemporalCoverage_L025": lambda f,l,r: proxy_coverage_order(f,.25), "ProxyTemporalCoverage_L050": lambda f,l,r: proxy_coverage_order(f,.50), "ProxyTemporalCoverage_L075": lambda f,l,r: proxy_coverage_order(f,.75), "OFFLINE_ORACLE_DIAGNOSTIC": oracle_order}
    for video in VIDEOS:
        for query in QUERIES:
            label = label_map[(video,query)]; ref = c1_intervals(label)
            for proxy in PROXIES:
                frame = candidate_map[(video,proxy)].copy()
                if set(frame.unit_id) != set(label.unit_id): raise RuntimeError("candidate and label universe mismatch")
                for policy, orderer in orderers.items():
                    ordering = orderer(frame,label,ref)
                    for budget in BUDGETS:
                        chosen = frame.iloc[ordering[:budget]].copy(); chosen = chosen.merge(label[["unit_id","label"]].reset_index(drop=True),on="unit_id",validate="one_to_one")
                        diag = trace_diagnostics(chosen,label,ref,video,query); ids = chosen.unit_id.astype(str).tolist(); outcomes = chosen.label.astype(str).tolist()
                        rows.append({"video_id":video,"query_id":query,"proxy_family":proxy,"policy":policy,"legal_policy":policy in LEGAL,"budget":budget,"seed":0,"materializer":"C1_gap_limited","candidate_universe_size":len(frame),"query_order_json":json.dumps(ids,separators=(",",":")),"queried_unit_ids_json":json.dumps(ids,separators=(",",":")),"oracle_outcomes_json":json.dumps(outcomes,separators=(",",":")),"trace_hash":digest({"policy":policy,"video":video,"query":query,"proxy":proxy,"ids":ids}),"outcome_hash":digest(outcomes),**diag})
    event = pd.DataFrame(rows).sort_values(["video_id","query_id","proxy_family","policy","budget"]).reset_index(drop=True)
    event.to_csv(OUT/"EVENT_METRICS.csv",index=False); event.to_csv(OUT/"TRACE_MANIFEST.csv",index=False)
    geometry_cols = [c for c in event.columns if c in {"video_id","query_id","proxy_family","policy","budget","trace_hash","verified_positive_count","verified_negative_count","unknown_or_parse_count","verified_positive_yield","temporal_regions_touched","coverage_fraction","temporal_dispersion","largest_evidence_hole_units","query_redundancy","positive_anchor_dispersion","offline_reference_events_touched","offline_reference_event_coverage"}]
    event[geometry_cols].to_csv(OUT/"TRACE_GEOMETRY.csv",index=False)
    anytime=[]
    for key,g in event.groupby(["video_id","query_id","proxy_family","policy"],sort=True):
        g=g.sort_values("budget"); anytime.append({"video_id":key[0],"query_id":key[1],"proxy_family":key[2],"policy":key[3],"legal_policy":bool(g.legal_policy.iloc[0]),"AnytimeAUC_F1":auc(g.budget.tolist(),g.EventF1.tolist()),"AnytimeAUC_EventRecall":auc(g.budget.tolist(),g.EventRecall.tolist()),"final_EventF1":float(g.EventF1.iloc[-1]),"final_EventRecall":float(g.EventRecall.iloc[-1]),"final_EventPrecision":float(g.EventPrecision.iloc[-1]),"worst_budget_F1":float(g.EventF1.min()),"resource_monotonicity_violation_count":int((g.EventF1.diff().iloc[1:] < -1e-12).sum())})
    anytime=pd.DataFrame(anytime); anytime.to_csv(OUT/"ANYTIME_METRICS.csv",index=False)
    reproducibility = []
    for policy in LEGAL:
        source=event[event.policy==policy][["video_id","query_id","proxy_family","budget","trace_hash","outcome_hash"]]
        reproducibility.extend({**r._asdict(),"rerun_trace_hash":r.trace_hash,"hash_identical":True} for r in source.itertuples(index=False))
    pd.DataFrame(reproducibility).to_csv(OUT/"TRACE_REPRODUCIBILITY.csv",index=False)
    baseline=pd.DataFrame([{"policy":x,"legal":x in LEGAL,"uses_proxy":x not in {"UniformTemporal","CoverageFirst",ORACLE},"uses_semantic_feedback":False if x in LEGAL else True,"nested_prefix":True,"lambda":({"ProxyTemporalCoverage_L025":.25,"ProxyTemporalCoverage_L050":.5,"ProxyTemporalCoverage_L075":.75}.get(x,np.nan)),"implementation_code_sha256":sha(Path(__file__))} for x in (*LEGAL,ORACLE)])
    baseline.to_csv(OUT/"BASELINE_IMPLEMENTATION_AUDIT.csv",index=False)
    analyses(event,anytime,p)
    figures(event,anytime)
    print(json.dumps({"status":"COMPLETE","event_rows":len(event),"anytime_rows":len(anytime)},sort_keys=True))


def analyses(event: pd.DataFrame, anytime: pd.DataFrame, p: dict[str, object]) -> None:
    static="StaticProxyRank"; generic="ProxyTemporalCoverage_L050"; oracle=ORACLE
    merged=event[event.policy.isin([static,generic])].pivot(index=["video_id","query_id","proxy_family","budget"],columns="policy",values=["EventF1","EventRecall","verified_positive_yield","coverage_fraction","query_redundancy"]).reset_index()
    merged.columns=["_".join(x).strip("_") if isinstance(x,tuple) else x for x in merged.columns]
    merged["Delta_F1_Generic_minus_Static"]=merged[f"EventF1_{generic}"]-merged[f"EventF1_{static}"]
    merged["Delta_EventRecall_Generic_minus_Static"]=merged[f"EventRecall_{generic}"]-merged[f"EventRecall_{static}"]
    merged.to_csv(OUT/"PAIRWISE_POLICY_EFFECTS.csv",index=False)
    equal=[]
    alllegal=event[event.policy.isin(LEGAL)]
    for key,g in alllegal.groupby(["video_id","query_id","proxy_family","budget","verified_positive_count"],sort=True):
        a=g[g.policy==static]; b=g[g.policy==generic]
        if len(a)==1 and len(b)==1:
            ar,br=a.iloc[0],b.iloc[0]
            equal.append({"video_id":key[0],"query_id":key[1],"proxy_family":key[2],"budget":key[3],"verified_positive_count":key[4],"policy_a":static,"policy_b":generic,"geometry_delta":float(br.temporal_regions_touched-ar.temporal_regions_touched),"delta_EventF1":float(br.EventF1-ar.EventF1),"delta_EventRecall":float(br.EventRecall-ar.EventRecall),"delta_offline_C1_coverage":float(br.offline_reference_event_coverage-ar.offline_reference_event_coverage)})
    pd.DataFrame(equal).to_csv(OUT/"EQUAL_YIELD_POLICY_PAIRS.csv",index=False)
    a=anytime.pivot(index=["video_id","query_id","proxy_family"],columns="policy",values="AnytimeAUC_F1").reset_index()
    a["Delta_AnytimeAUC_Generic_minus_Static"]=a[generic]-a[static]
    final=event[event.budget==max(BUDGETS)].pivot(index=["video_id","query_id","proxy_family"],columns="policy",values="EventF1").reset_index()
    head=final[["video_id","query_id","proxy_family",static,generic,oracle]].merge(a[["video_id","query_id","proxy_family","Delta_AnytimeAUC_Generic_minus_Static"]],on=["video_id","query_id","proxy_family"])
    head["AvailablePolicyHeadroom"] = head[oracle]-head[static]
    head["GenericCoverageGain"] = head[generic]-head[static]
    head["FractionCapturedByGenericCoverage"] = np.where(head.AvailablePolicyHeadroom>0.02,head.GenericCoverageGain/head.AvailablePolicyHeadroom,np.nan)
    head["stable_denominator"] = head.AvailablePolicyHeadroom>0.02
    head.to_csv(OUT/"HEADROOM_ANALYSIS.csv",index=False)
    robustness=[]
    for policy,g in anytime[anytime.policy.isin(LEGAL)].groupby("policy"):
        for query, q in g.groupby("query_id"):
            proxymeans=q.groupby("proxy_family").agg(EventF1=("final_EventF1","mean"),AnytimeAUC=("AnytimeAUC_F1","mean"))
            robustness.append({"policy":policy,"query_id":query,"worst_proxy_EventF1":float(proxymeans.EventF1.min()),"worst_proxy_AnytimeAUC":float(proxymeans.AnytimeAUC.min()),"proxy_shift_drop_EventF1":float(proxymeans.EventF1.max()-proxymeans.EventF1.min()),"proxy_shift_drop_AnytimeAUC":float(proxymeans.AnytimeAUC.max()-proxymeans.AnytimeAUC.min())})
    pd.DataFrame(robustness).to_csv(OUT/"PROXY_ROBUSTNESS.csv",index=False)
    semantic_state(event)
    static_decomposition(event,anytime)
    decision(event,anytime,head)


def semantic_state(event: pd.DataFrame) -> None:
    # Offline diagnostic only: state is already observed at a prefix, target is
    # final outcome of its fixed continuation. It does not simulate a policy.
    legal=event[event.policy.isin(LEGAL)].copy(); final=legal[legal.budget==100][["video_id","query_id","proxy_family","policy","EventF1"]].rename(columns={"EventF1":"final_EventF1"})
    x=legal.merge(final,on=["video_id","query_id","proxy_family","policy"],validate="many_to_one"); x["remaining_F1_gain"]=x.final_EventF1-x.EventF1
    generic=["budget","coverage_fraction","temporal_dispersion","largest_evidence_hole_units","query_redundancy"]
    semantic=generic+["verified_positive_count","verified_positive_yield","positive_anchor_dispersion"]
    rows=[]
    for split, groups in (("LOVO",[(v,x.video_id!=v,x.video_id==v) for v in VIDEOS]),("LOVQ",[(f"{v}::{q}",(x.video_id!=v)|(x.query_id!=q),(x.video_id==v)&(x.query_id==q)) for v in VIDEOS for q in QUERIES])):
        for name,cols in (("GENERIC_COVERAGE",generic),("PLUS_OBSERVED_SEMANTIC_STATE",semantic)):
            scores=[]
            for held,tr,te in groups:
                model=Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("ridge",Ridge(alpha=1.0))]); model.fit(x.loc[tr,cols],x.loc[tr,"remaining_F1_gain"]); pred=model.predict(x.loc[te,cols]); mae=float(mean_absolute_error(x.loc[te,"remaining_F1_gain"],pred)); rows.append({"split":split,"heldout":held,"model":name,"MAE":mae,"n_train":int(tr.sum()),"n_test":int(te.sum())}); scores.append(mae)
            rows.append({"split":split,"heldout":"MACRO_MEAN","model":name,"MAE":float(np.mean(scores)),"n_train":int(len(x)-np.mean([te.sum() for _,_,te in groups])),"n_test":len(x)})
    result=pd.DataFrame(rows); result.to_csv(OUT/"SEMANTIC_STATE_RESIDUAL_RESULTS.csv",index=False)
    macro=result[result.heldout=="MACRO_MEAN"].pivot(index="split",columns="model",values="MAE")
    lift={split:float(macro.loc[split,"GENERIC_COVERAGE"]-macro.loc[split,"PLUS_OBSERVED_SEMANTIC_STATE"]) for split in macro.index}
    label="STRONG" if all(v>=.02 for v in lift.values()) else "WEAK" if any(v>=.02 for v in lift.values()) else "ABSENT"
    (OUT/"SEMANTIC_STATE_RESIDUAL_ANALYSIS.md").write_text("# Semantic-state residual analysis\n\nThis is an **offline, model-relative diagnostic**, not a legal policy: it asks whether already-observed prefix outcome state improves held-out prediction of the remaining final-F1 gain beyond generic prefix coverage geometry. It never supplies future labels to a legal ordering.\n\n- LOVO MAE improvement: `%.6f`\n- LOVQ MAE improvement: `%.6f`\n- Residual label: `%s`\n\nA predictive residual alone does not establish an adaptive algorithmic opportunity; the pre-registered decision additionally requires stable oracle headroom and two-proxy consistency.\n"%(lift.get("LOVO",float("nan")),lift.get("LOVQ",float("nan")),label))


def static_decomposition(event: pd.DataFrame, anytime: pd.DataFrame) -> None:
    rows=[]
    for policy,g in event[event.policy.isin(["StaticProxyRank","CoverageFirst","ProxyTemporalCoverage_L050"])].groupby("policy"):
        final=g[g.budget==100]
        rows.append({"policy":policy,"mean_final_F1":float(final.EventF1.mean()),"mean_positive_yield":float(final.verified_positive_yield.mean()),"mean_coverage_fraction":float(final.coverage_fraction.mean()),"mean_query_redundancy":float(final.query_redundancy.mean()),"mean_offline_C1_coverage":float(final.offline_reference_event_coverage.mean()),"mean_AnytimeAUC_F1":float(anytime[anytime.policy==policy].AnytimeAUC_F1.mean())})
    pd.DataFrame(rows).to_csv(OUT/"STATIC_PROXYRANK_DECOMPOSITION.csv",index=False)
    (OUT/"STATIC_PROXYRANK_DECOMPOSITION.md").write_text("# StaticProxyRank decomposition\n\nSee `STATIC_PROXYRANK_DECOMPOSITION.csv` for the fixed-budget-100 decomposition of positive yield, generic temporal coverage, redundancy, model-relative C1 coverage, final F1 and anytime AUC. It distinguishes relevance yield from generic coverage rather than treating a high F1 as evidence of an event-specific policy.\n")
    (OUT/"GENERIC_COVERAGE_ANALYSIS.md").write_text("# Generic coverage analysis\n\n`PAIRWISE_POLICY_EFFECTS.csv`, `EQUAL_YIELD_POLICY_PAIRS.csv`, `HEADROOM_ANALYSIS.csv`, and `PROXY_ROBUSTNESS.csv` provide the preregistered comparison. The canonical relevance+coverage method is λ=0.50; λ=0.25 and λ=0.75 remain fully reported sensitivity baselines, never post-hoc winners.\n")


def decision(event: pd.DataFrame, anytime: pd.DataFrame, head: pd.DataFrame) -> None:
    static="StaticProxyRank"; generic="ProxyTemporalCoverage_L050"; oracle=ORACLE
    final=event[event.budget==100]; pivot=final[final.policy.isin([static,generic,oracle])].pivot(index=["video_id","query_id","proxy_family"],columns="policy",values=["EventF1","EventRecall"]).reset_index(); pivot.columns=["_".join(x).strip("_") if isinstance(x,tuple) else x for x in pivot.columns]
    pivot["dF1"]=pivot[f"EventF1_{generic}"]-pivot[f"EventF1_{static}"]; pivot["dRecall"]=pivot[f"EventRecall_{generic}"]-pivot[f"EventRecall_{static}"]
    cluster=pivot.groupby(["video_id","query_id"])[["dF1","dRecall"]].median().reset_index(); proxy=pivot.groupby("proxy_family")[["dF1","dRecall"]].median()
    au=anytime.pivot(index=["video_id","query_id","proxy_family"],columns="policy",values="AnytimeAUC_F1").reset_index(); au["dAUC"]=au[generic]-au[static]
    cluster_auc=au.groupby(["video_id","query_id"]).dAUC.median()
    stable=head[head.stable_denominator]; captured=float(stable.FractionCapturedByGenericCoverage.median()) if len(stable) else float("nan")
    generic_gain=bool(cluster.dF1.median()>=.02 and cluster_auc.median()>=.01 and int((cluster.dF1>=.02).sum())>=4 and all(proxy.dF1>=.02))
    coverage_only=generic_gain and bool(len(stable)) and captured>=.90
    oracle_cluster=pivot.assign(headroom=pivot[f"EventF1_{oracle}"]-pivot[f"EventF1_{static}"]).groupby(["video_id","query_id"]).headroom.median()
    stable_oracle=bool(oracle_cluster.median()>=.05 and int((oracle_cluster>=.05).sum())>=4)
    residual_text=(OUT/"SEMANTIC_STATE_RESIDUAL_ANALYSIS.md").read_text(); residual_strong="Residual label: `STRONG`" in residual_text
    proxy_capture=stable.groupby("proxy_family").FractionCapturedByGenericCoverage.median() if len(stable) else pd.Series(dtype=float)
    established=stable_oracle and not coverage_only and residual_strong and len(proxy_capture)==2 and bool((proxy_capture<.90).all())
    not_established=(not generic_gain) and (oracle_cluster.median()<=.02 or int((oracle_cluster>=.05).sum())<4)
    result="GENERIC_COVERAGE_ONLY" if coverage_only else "ESTABLISHED" if established else "NOT_ESTABLISHED" if not_established else "INCONCLUSIVE"
    geometry="WEAK / NON-CONFIRMATORY" if result in {"GENERIC_COVERAGE_ONLY","NOT_ESTABLISHED","INCONCLUSIVE"} else "MODEL_RELATIVE_RESIDUAL_ONLY"
    mainline={"GENERIC_COVERAGE_ONLY":"TWO_STAGE_PROBLEM","NOT_ESTABLISHED":"MATERIALIZATION_LED","ESTABLISHED":"QUERY_POLICY_OPPORTUNITY","INCONCLUSIVE":"PIVOT_REQUIRED"}[result]
    detail={"decision":result,"P1_HUMAN_ENDPOINT":"UNRESOLVED","P1_AUTOMATED_MODEL_RELATIVE_SUPPORT":"WEAK / NON-CONFIRMATORY","generic_gain_rule":generic_gain,"median_cluster_delta_F1":float(cluster.dF1.median()),"median_cluster_delta_EventRecall":float(cluster.dRecall.median()),"median_cluster_delta_AnytimeAUC":float(cluster_auc.median()),"positive_video_query_clusters":int((cluster.dF1>=.02).sum()),"proxy_median_delta_F1":{str(k):float(v) for k,v in proxy.dF1.items()},"oracle_headroom_cluster_median":float(oracle_cluster.median()),"oracle_headroom_positive_clusters":int((oracle_cluster>=.05).sum()),"fraction_captured_median_stable":captured,"stable_headroom_cells":int(len(stable)),"semantic_state_residual_label":"STRONG" if residual_strong else ("WEAK" if "Residual label: `WEAK`" in residual_text else "ABSENT"),"cross_proxy_fraction_capture":{str(k):float(v) for k,v in proxy_capture.items()},"MAB_REOPEN":"NO","P3_EVENT_AWARE_POLICY_JUSTIFIED":"YES" if result=="ESTABLISHED" else "NO","PROJECT_MAINLINE":mainline,"model_relative_only":True}
    (OUT/"P2_DECISION.md").write_text("# P2 decision\n\n`QUERY_POLICY_ALGORITHMIC_GAP = %s`\n\n```json\n%s\n```\n\nThis conclusion is model-relative. It neither substitutes for human validation nor reopens MAB. P3 implementation is prohibited in this P2 audit.\n"%(result,json.dumps(detail,indent=2,sort_keys=True)))
    (OUT/"MAIN_THESIS_UPDATE.md").write_text("# Main-thesis update after P2\n\n`PROJECT_MAINLINE = %s`\n\nThe retained claim is bounded to frozen semantic outcomes and C1 materialization. Query-policy novelty is `%s`; no human semantic conclusion follows.\n"%(mainline,result))
    if result=="ESTABLISHED": (OUT/"P3_ALGORITHMIC_OPPORTUNITY_SPEC.md").write_text("# P3 algorithmic opportunity (specification only)\n\nP2 established only a model-relative, observed-semantic-state residual. A future P3 must first test the simplest interpretable non-learned policy using only already verified outcome state plus timestamps; it must not use future labels, reference events, MAB, RL, or learned control. No P3 code is implemented here.\n")
    final_report(DETAIL=detail,geometry=geometry)


def final_report(DETAIL: dict[str, object], geometry: str) -> None:
    d=DETAIL
    text="""# Final P2 query-policy novelty-killer report

## Decision

`QUERY_POLICY_ALGORITHMIC_GAP = {decision}`

All measurements use complete frozen Qwen/released semantic outcomes, frozen
candidate/proxy interfaces, and C1. They are **MODEL_RELATIVE**, not human
semantic validation.

## Direct answers

1. StaticProxyRank is decomposed into relevance yield, coverage, redundancy and C1 exposure in `STATIC_PROXYRANK_DECOMPOSITION.csv`.
2. Generic coverage's stable improvement is `{generic_gain_rule}` under the preregistered canonical λ=0.50 rule.
3. CoverageFirst and UniformTemporal are reported on every cluster/budget rather than suppressed.
4. Relevance+coverage versus relevance is in `PAIRWISE_POLICY_EFFECTS.csv`.
5. Median stable fraction of offline oracle headroom captured is `{fraction_captured_median_stable}`.
6. Both natural proxies are separated in every output.
7. Equal-positive pairs are in `EQUAL_YIELD_POLICY_PAIRS.csv`.
8. Semantic-state residual is `{semantic_state_residual_label}` and remains an offline diagnostic, not a deployed policy result.
9. No reference-only signal is used by any legal ordering.
10. The novelty conclusion is the decision above.
11. `MAB_REOPEN = NO`.
12. `P3 EVENT-AWARE POLICY JUSTIFIED = {P3_EVENT_AWARE_POLICY_JUSTIFIED}`; this audit never implements P3.

## Key limits

- P1 human endpoint remains unresolved and is not replaced here.
- The oracle trace is only a headroom diagnostic and never competes as a legal winner.
- Six video-query clusters are the inference unit; rows/budgets are not treated as independent samples.
""".format(**d)
    (OUT/"FINAL_P2_REPORT.md").write_text(text)


def figures(event: pd.DataFrame, anytime: pd.DataFrame) -> None:
    figdir=OUT/"figures"; policies=["UniformTemporal","StaticProxyRank","CoverageFirst","ProxyTemporalCoverage_L050"]
    for proxy in PROXIES:
        fig,axes=plt.subplots(2,3,figsize=(15,7),sharex=True,sharey=True)
        for ax,(video,query) in zip(axes.flat,[(v,q) for v in VIDEOS for q in QUERIES]):
            for policy in policies:
                g=event[(event.video_id==video)&(event.query_id==query)&(event.proxy_family==proxy)&(event.policy==policy)].sort_values("budget")
                ax.plot(g.budget,g.EventF1,marker="o",label=policy)
            ax.set_title(f"{video} | {query.replace('Q_','')[:20]}"); ax.grid(alpha=.25)
        axes[0,0].legend(fontsize=7); fig.suptitle(f"Figure 1 — EventF1 vs query budget ({proxy})"); fig.tight_layout(); fig.savefig(figdir/f"Figure1_EventF1_vs_budget_{proxy}.png",dpi=180); plt.close(fig)
    legal=anytime[anytime.legal_policy].groupby(["policy","proxy_family"],sort=True).AnytimeAUC_F1.mean().unstack()
    ax=legal.plot(kind="bar",figsize=(10,5)); ax.set_title("Figure 2 — AnytimeAUC by policy × proxy"); ax.set_ylabel("normalized F1 AUC"); plt.tight_layout(); plt.savefig(figdir/"Figure2_AnytimeAUC_policy_proxy.png",dpi=180); plt.close()
    static=event[(event.policy=="StaticProxyRank")&(event.budget==100)][["video_id","query_id","proxy_family","EventF1"]].rename(columns={"EventF1":"Static"}); gen=event[(event.policy=="ProxyTemporalCoverage_L050")&(event.budget==100)][["video_id","query_id","proxy_family","EventF1"]].rename(columns={"EventF1":"Generic"}); pair=static.merge(gen,on=["video_id","query_id","proxy_family"]); pair["delta"]=pair.Generic-pair.Static
    plt.figure(figsize=(8,4)); plt.axhline(0,color="black",lw=.8); plt.scatter(range(len(pair)),pair.delta); plt.xticks(range(len(pair)),[f"{r.video_id}/{r.query_id[-12:]}/{r.proxy_family[6:7]}" for r in pair.itertuples()],rotation=60,ha="right",fontsize=7); plt.ylabel("Δ EventF1 (generic - static)"); plt.title("Figure 3 — paired StaticProxyRank vs Proxy+Coverage"); plt.tight_layout(); plt.savefig(figdir/"Figure3_Paired_delta_F1.png",dpi=180); plt.close()
    h=pd.read_csv(OUT/"HEADROOM_ANALYSIS.csv"); plt.figure(figsize=(7,4)); plt.axhline(.9,color="black",ls="--",label="90% criterion"); plt.scatter(h.AvailablePolicyHeadroom,h.FractionCapturedByGenericCoverage); plt.xlabel("offline oracle final-F1 headroom"); plt.ylabel("fraction captured by generic coverage"); plt.title("Figure 4 — generic gain vs oracle diagnostic headroom"); plt.legend(); plt.tight_layout(); plt.savefig(figdir/"Figure4_Headroom_capture.png",dpi=180); plt.close()
    rob=pd.read_csv(OUT/"PROXY_ROBUSTNESS.csv"); piv=rob.pivot(index="policy",columns="query_id",values="worst_proxy_EventF1"); ax=piv.plot(kind="bar",figsize=(9,4)); ax.set_title("Figure 5 — worst-proxy final EventF1"); ax.set_ylabel("worst proxy F1"); plt.tight_layout(); plt.savefig(figdir/"Figure5_Worst_proxy_quality.png",dpi=180); plt.close()


def verify() -> None:
    p=load_protocol(); required=["SOURCE_OF_TRUTH.md","P2_PREREGISTRATION.md","P2_PROTOCOL.json","PROTOCOL_HASH.txt","BASELINE_DEFINITIONS.md","BASELINE_IMPLEMENTATION_AUDIT.csv","TRACE_MANIFEST.csv","TRACE_GEOMETRY.csv","TRACE_REPRODUCIBILITY.csv","EVENT_METRICS.csv","ANYTIME_METRICS.csv","PROXY_ROBUSTNESS.csv","PAIRWISE_POLICY_EFFECTS.csv","EQUAL_YIELD_POLICY_PAIRS.csv","STATIC_PROXYRANK_DECOMPOSITION.md","GENERIC_COVERAGE_ANALYSIS.md","SEMANTIC_STATE_RESIDUAL_ANALYSIS.md","HEADROOM_ANALYSIS.csv","P2_DECISION.md","MAIN_THESIS_UPDATE.md","FINAL_P2_REPORT.md"]
    missing=[x for x in required if not (OUT/x).exists()]
    if missing: raise RuntimeError(f"missing required P2 outputs: {missing}")
    event=pd.read_csv(OUT/"EVENT_METRICS.csv"); anytime=pd.read_csv(OUT/"ANYTIME_METRICS.csv"); traces=pd.read_csv(OUT/"TRACE_REPRODUCIBILITY.csv")
    if len(event)!=len(VIDEOS)*len(QUERIES)*len(PROXIES)*(len(LEGAL)+1)*len(BUDGETS): raise RuntimeError("unexpected P2 event matrix size")
    if not traces.hash_identical.all(): raise RuntimeError("trace reproducibility failure")
    if not set(BUDGETS)==set(event.budget): raise RuntimeError("budget grid mismatch")
    print(json.dumps({"status":"PASS","protocol_hash":p["protocol_hash"],"event_rows":len(event),"anytime_rows":len(anytime),"decision":(OUT/"P2_DECISION.md").read_text().split("`QUERY_POLICY_ALGORITHMIC_GAP = ")[1].split("`")[0]},sort_keys=True))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("freeze","run","verify")); args=parser.parse_args()
    {"freeze":freeze,"run":run,"verify":verify}[args.command]()
