#!/usr/bin/env python3
"""Cached-replay audit of proxy robustness and budgeted query execution.

The workflow deliberately separates ``freeze`` from ``run``.  Freeze reads
only candidate/proxy assets and repository provenance.  It defines all
outcome-blind proxy perturbations, policies, budgets, metrics, interaction
cells, and decision thresholds before the released semantic unit labels are
joined.  Run then performs deterministic cached replay with the already
supported C1 gap-only materializer; it never invokes a semantic model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/main_thesis_alignment_v1"
P0_OUT = ROOT / "outputs/p0_materializer_validation_v3"
MECH_OUT = ROOT / "outputs/p0_materializer_mechanism_ablation_v1"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
SCAN = ROOT / "outputs/v3_scan_proxy_preregistration_v1"
P0_RUNNER = ROOT / "scripts/run_p0_v3_materializer_validation.py"
MECH_RUNNER = ROOT / "scripts/analyze_p0_v3_materializer_mechanisms.py"

VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
QUERY_ID = "Q_DRIVER_RESPONSE_V1"
BUDGETS = (5, 10, 20, 50, 80, 100)
POLICIES = ("UniformTemporal", "StaticProxyRank", "TemporalCoverage")
DEGRADATION_SEED = 20260811
EPSILON = 1e-12

REGIMES: tuple[dict[str, Any], ...] = (
    {
        "regime": "R0_ORIGINAL",
        "axis": "none",
        "level": "original",
        "construction": "Frozen prospective YOLO proxy and complete one-candidate-per-unit universe.",
        "rank_mix_alpha": 0.0,
        "keep_rate": 1.0,
    },
    {
        "regime": "R1_RANK_MILD_A025",
        "axis": "ranking",
        "level": "mild",
        "construction": "score=(1-0.25)*original+0.25*SHA256-uniform(candidate_id,seed); full exposure.",
        "rank_mix_alpha": 0.25,
        "keep_rate": 1.0,
    },
    {
        "regime": "R2_RANK_MEDIUM_A050",
        "axis": "ranking",
        "level": "medium",
        "construction": "score=(1-0.50)*original+0.50*SHA256-uniform(candidate_id,seed); full exposure.",
        "rank_mix_alpha": 0.50,
        "keep_rate": 1.0,
    },
    {
        "regime": "R3_RANK_SEVERE_HASH",
        "axis": "ranking",
        "level": "severe",
        "construction": "score=SHA256-uniform(candidate_id,seed); full exposure and no semantic-label input.",
        "rank_mix_alpha": 1.0,
        "keep_rate": 1.0,
    },
    {
        "regime": "E1_EXPOSURE_MILD_KEEP080",
        "axis": "exposure",
        "level": "mild",
        "construction": "Keep candidate iff SHA256-uniform(candidate_id,seed,exposure)<0.80; retain original score.",
        "rank_mix_alpha": 0.0,
        "keep_rate": 0.80,
    },
    {
        "regime": "E2_EXPOSURE_MEDIUM_KEEP060",
        "axis": "exposure",
        "level": "medium",
        "construction": "Keep candidate iff SHA256-uniform(candidate_id,seed,exposure)<0.60; retain original score.",
        "rank_mix_alpha": 0.0,
        "keep_rate": 0.60,
    },
    {
        "regime": "E3_EXPOSURE_SEVERE_KEEP040",
        "axis": "exposure",
        "level": "severe",
        "construction": "Keep candidate iff SHA256-uniform(candidate_id,seed,exposure)<0.40; retain original score.",
        "rank_mix_alpha": 0.0,
        "keep_rate": 0.40,
    },
)

INTERACTION_REGIMES = ("R0_ORIGINAL", "R3_RANK_SEVERE_HASH", "E3_EXPOSURE_SEVERE_KEEP040")
INTERACTION_POLICIES = ("StaticProxyRank", "TemporalCoverage")
INTERACTION_BUDGETS = (10, 50, 100)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_once(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def csv_payload(rows: Sequence[dict[str, Any]], fields: Sequence[str] | None = None) -> str:
    import io

    if fields is None:
        fields = list(rows[0]) if rows else ["empty"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_csv_once(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str] | None = None) -> None:
    text = csv_payload(rows, fields)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_text_once(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def finite(value: float | int | None) -> float | int | str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return ""
    return value


def deterministic_uniform(candidate_id: str, regime: str, channel: str) -> float:
    token = f"{DEGRADATION_SEED}|{regime}|{channel}|{candidate_id}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
    return integer / float(1 << 64)


def p0_module():
    spec = importlib.util.spec_from_file_location("main_thesis_p0_runner", P0_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen P0 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def mechanism_module():
    spec = importlib.util.spec_from_file_location("main_thesis_mechanism_runner", MECH_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen mechanism runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_artifacts() -> dict[str, dict[str, str]]:
    paths = [
        P0_RUNNER,
        MECH_RUNNER,
        P0_OUT / "EXPERIMENT_PROTOCOL.json",
        P0_OUT / "pooled_summary.json",
        MECH_OUT / "MECHANISM_PROTOCOL.json",
        MECH_OUT / "mechanism_summary.csv",
        V10 / "FINAL_UNIT_REFERENCE.parquet",
        V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet",
        V10 / "REFERENCE_MANIFEST.json",
        SCAN / "FROZEN_V3_SCAN_PROXY_PROTOCOL.json",
        ROOT / "configs/research_contract_v1.yaml",
        ROOT / "configs/scan_confirm_myopic_vps.yaml",
        ROOT / "configs/fixed_ratio_25_75.yaml",
        ROOT / "docs/PSVR_P0_P1_P2_EXPERIMENT_CONTRACT.md",
        ROOT / "MAB_RESEARCH_DIRECTION_DECISION.md",
        ROOT / "outputs/public_state_predictability_cached_v3/SUMMARY.json",
        ROOT / "outputs/controller_dynamic_headroom_cached_v1/SUMMARY.json",
        ROOT / "outputs/psvr_bottleneck_research/AUDITED_DECISION.json",
    ]
    for video in VIDEOS:
        paths.extend([
            SCAN / "frozen_tables" / video / "candidate_table.parquet",
            SCAN / "frozen_tables" / video / "proxy_table.parquet",
        ])
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"missing frozen input artifacts: {missing}")
    return {rel(path): {"sha256": sha256_file(path)} for path in paths}


def load_candidate_proxy_only() -> dict[str, list[dict[str, Any]]]:
    """Load only public candidate/proxy fields; freeze must not read labels."""
    out: dict[str, list[dict[str, Any]]] = {}
    for video in VIDEOS:
        candidate = pd.read_parquet(SCAN / "frozen_tables" / video / "candidate_table.parquet")
        proxy = pd.read_parquet(SCAN / "frozen_tables" / video / "proxy_table.parquet")
        merged = candidate.merge(proxy, on=["video_id", "candidate_id"], validate="one_to_one")
        rows = []
        for row in merged.sort_values(["candidate_order", "candidate_id"]).to_dict(orient="records"):
            source = list(row["source_unit_ids"])
            if len(source) != 1:
                raise RuntimeError(f"candidate does not bind one unit: {row['candidate_id']}")
            rows.append({**row, "unit_id": source[0]})
        out[video] = rows
    return out


def construct_regime(rows: Sequence[dict[str, Any]], definition: dict[str, Any]) -> list[dict[str, Any]]:
    regime = definition["regime"]
    keep_rate = float(definition["keep_rate"])
    alpha = float(definition["rank_mix_alpha"])
    out: list[dict[str, Any]] = []
    for original in rows:
        if keep_rate < 1.0:
            keep = deterministic_uniform(original["candidate_id"], regime, "exposure") < keep_rate
            if not keep:
                continue
        noise = deterministic_uniform(original["candidate_id"], regime, "ranking")
        row = dict(original)
        row["original_proxy_score"] = float(original["proxy_score"])
        row["proxy_score"] = (1.0 - alpha) * float(original["proxy_score"]) + alpha * noise
        row["proxy_regime"] = regime
        out.append(row)
    return out


def frozen_protocol() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    public = load_candidate_proxy_only()
    manifest_rows: list[dict[str, Any]] = []
    for definition in REGIMES:
        for video in VIDEOS:
            rows = construct_regime(public[video], definition)
            if len(rows) < max(BUDGETS):
                raise RuntimeError(f"{definition['regime']} {video} leaves fewer than 100 candidates")
            scores = np.asarray([float(row["proxy_score"]) for row in rows], dtype=float)
            manifest_rows.append({
                "regime": definition["regime"],
                "video_id": video,
                "axis": definition["axis"],
                "level": definition["level"],
                "construction": definition["construction"],
                "seed": DEGRADATION_SEED,
                "GT_blind_construction": True,
                "original_candidate_rows": len(public[video]),
                "candidate_rows": len(rows),
                "structural_candidate_coverage": len(rows) / len(public[video]),
                "score_min": float(scores.min()),
                "score_mean": float(scores.mean()),
                "score_max": float(scores.max()),
                "regime_table_hash": canonical_hash([
                    [r["candidate_id"], int(r["candidate_order"]), float(r["proxy_score"])] for r in rows
                ]),
            })

    protocol: dict[str, Any] = {
        "protocol_id": "GVAQP_MAIN_THESIS_PROXY_ROBUSTNESS_CACHED_REPLAY_V1",
        "status": "FROZEN_BEFORE_PROXY_STRESS_EVENT_RESULTS",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "known_prior_evidence": {
            "P0_materializer_results_already_observed": True,
            "median_K3_minus_K0_F1": 0.1457,
            "median_C1_minus_C0_F1": 0.1377,
            "new_proxy_stress_results_observed_before_freeze": False,
        },
        "semantic_inference": "NONE; deterministic cached replay only",
        "evaluation_kind": "MODEL_RELATIVE_EVALUATION_AGAINST_FROZEN_FULL_GRID_K3_EVENT_RELATION",
        "reference_circularity": "QUALIFIED_BUT_VALID; this audit does not independently establish human event continuity",
        "videos": list(VIDEOS),
        "query_id": QUERY_ID,
        "materializer": {
            "name": "C1_gap_limited",
            "definition": "Merge consecutive queried relevant 10-second units iff gap <= 10.0 seconds; no duration cap, negative barrier, or K3 extras.",
            "gap_sec": 10.0,
            "source": "scripts/analyze_p0_v3_materializer_mechanisms.py:generic_events",
            "frozen_from_P0_mechanism_ablation": True,
        },
        "policies": [
            {"name": "UniformTemporal", "uses_proxy": False, "nested_across_budget": False,
             "note": "P0 exact evenly spaced subset; budget curves replace positions and are not strict anytime prefixes."},
            {"name": "StaticProxyRank", "uses_proxy": True, "nested_across_budget": True,
             "note": "Descending regime proxy score with candidate-order/id tie break."},
            {"name": "TemporalCoverage", "uses_proxy": False, "nested_across_budget": True,
             "note": "P0 recursive temporal bisection over the regime candidate universe."},
        ],
        "excluded_primary_policies": {
            "FixedRatio_scan_confirm": "Historical physical controller has progressive SCAN exposure and seconds-based costs, not the current precomputed candidate/query-count replay interface.",
            "Ours": "Ambiguous historical name, not a single deterministic versioned policy.",
            "MAB_or_learned_controller": "Explicitly excluded; this audit first tests whether an adaptive opportunity exists.",
        },
        "budgets": list(BUDGETS),
        "budget_semantics": "QUERY_BUDGET / cached semantic-oracle invocation count; not seconds and not a physical deadline",
        "regime_definitions": list(REGIMES),
        "natural_variant_audit": {
            "compatible_current_variants_found": 1,
            "included_natural_variant": "R0_ORIGINAL prospective YOLOv8n V3 contract",
            "excluded_historical_assets": "Other YOLO/PSVR/RC-SEM proxy artifacts use different source videos, units, candidate semantics, or schemas; they are not promoted into this common-universe matrix.",
            "synthetic_degradation_reason": "No reproducible GOOD/MEDIUM/POOR natural variants share the released DALI/HANGZHOU/WUHAN V3 interface.",
        },
        "degradation_integrity": {
            "reads_semantic_labels": False,
            "reads_reference_events": False,
            "hash_inputs": ["degradation_seed", "regime_id", "channel", "candidate_id"],
            "ranking_axis": "convex mixing with deterministic SHA256-uniform score; candidate universe unchanged",
            "exposure_axis": "deterministic SHA256 thinning; original scores retained",
            "not_tuned_on_event_F1": True,
        },
        "primary_metric": "Event F1 using frozen P0 overlap-any one-to-one matcher",
        "secondary_metrics": ["Event precision", "Event recall", "TP/FP/FN", "unique events recovered", "oracle calls", "candidate coverage"],
        "resource_analysis": {
            "monotonicity_epsilon": EPSILON,
            "primary_monotonicity_policies": ["StaticProxyRank", "TemporalCoverage"],
            "uniform_curve_qualification": "UniformTemporal exact subsets are non-nested and diagnostic, not a strict anytime execution trace.",
            "normalized_budget_axis": [b / max(BUDGETS) for b in BUDGETS],
            "anytime_auc_origin": [0.0, 0.0],
            "gap_summary_budgets": {"low": 5, "medium": 20, "high": 100},
        },
        "proxy_gap_axes": {
            "ranking": {"good": "R0_ORIGINAL", "poor": "R3_RANK_SEVERE_HASH"},
            "exposure": {"good": "R0_ORIGINAL", "poor": "E3_EXPOSURE_SEVERE_KEEP040"},
        },
        "interaction_subset": {
            "regimes": list(INTERACTION_REGIMES),
            "policies": list(INTERACTION_POLICIES),
            "budgets": list(INTERACTION_BUDGETS),
            "videos": list(VIDEOS),
            "materializers": ["C0_naive_all_positive_span", "C1_gap_limited"],
            "systematic_interaction_threshold_F1": 0.05,
            "systematic_rule": "range of regime-policy median C1-C0 effects >=0.05 and the ordering direction recurs on at least two videos",
        },
        "decision_thresholds_frozen_before_results": {
            "proxy_bottleneck_yes_gap_F1": 0.10,
            "proxy_bottleneck_partial_gap_F1": 0.03,
            "proxy_bottleneck_cross_video_requirement": 2,
            "resource_monotonicity_yes_max_violation_rate": 0.05,
            "resource_monotonicity_partial_max_violation_rate": 0.25,
            "gap_compression_yes": 0.50,
            "gap_compression_partial": 0.0,
            "policy_effect_substantial_median_spread_F1": 0.10,
            "policy_matters_more_poor_margin_F1": 0.02,
            "historical_materializer_effect_F1": 0.1457,
            "mainline_rules": {
                "QUERY_POLICY_MAINLINE": "proxy bottleneck YES/PARTIAL; policy effect substantial or poor-proxy robustness unresolved; no systematic two-stage interaction required",
                "MATERIALIZATION_MAINLINE": "proxy bottleneck NO; policy effect below 0.10; historical materializer effect remains larger",
                "TWO_STAGE_UNIFIED": "proxy bottleneck YES/PARTIAL; policy effect >=0.10; historical C1 effect >=0.10; interaction systematic",
                "PIVOT_REQUIRED": "proxy bottleneck NO; materialization independent support weak; action opportunity ABSENT/WEAK and neither stage has substantial current effect",
            },
        },
        "robust_policy_selection": "Lexicographically maximize worst of mean rank-poor and exposure-poor F1, then poor-regime mean Anytime AUC, then minimize nested-policy monotonicity violation rate.",
        "statistics": {"bootstrap_seed": 20260811, "bootstrap_resamples": 10000},
        "input_artifacts": source_artifacts(),
        "runner": {"path": rel(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        "repo_commit": git("rev-parse", "HEAD"),
        "repo_branch": git("branch", "--show-current"),
        "dirty_worktree": git("status", "--short").splitlines(),
    }
    protocol["protocol_hash"] = canonical_hash({k: v for k, v in protocol.items() if k not in {"created_at_utc", "protocol_hash"}})
    return protocol, manifest_rows


def freeze() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite nonempty output directory: {OUT}")
    protocol, manifest = frozen_protocol()
    OUT.mkdir(parents=True)
    write_json_once(OUT / "AUDIT_PROTOCOL.json", protocol)
    write_text_once(OUT / "PROTOCOL_HASH.txt", protocol["protocol_hash"] + "\n")
    write_csv_once(OUT / "PROXY_REGIME_MANIFEST.csv", manifest)
    print(json.dumps({"status": "FROZEN", "protocol_hash": protocol["protocol_hash"], "regime_rows": len(manifest)}))


def load_protocol() -> dict[str, Any]:
    protocol = read_json(OUT / "AUDIT_PROTOCOL.json")
    actual = canonical_hash({k: v for k, v in protocol.items() if k not in {"created_at_utc", "protocol_hash"}})
    if actual != protocol["protocol_hash"] or (OUT / "PROTOCOL_HASH.txt").read_text().strip() != actual:
        raise RuntimeError("audit protocol hash mismatch")
    if sha256_file(Path(__file__)) != protocol["runner"]["sha256"]:
        raise RuntimeError("runner changed after protocol freeze")
    for path_text, metadata in protocol["input_artifacts"].items():
        path = ROOT / path_text
        if sha256_file(path) != metadata["sha256"]:
            raise RuntimeError(f"input artifact changed after freeze: {path_text}")
    return protocol


def enrich_candidates(
    public: dict[str, list[dict[str, Any]]],
    labels: dict[str, Any],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for definition in REGIMES:
        for video in VIDEOS:
            rows = construct_regime(public[video], definition)
            for row in rows:
                if row["unit_id"] not in labels:
                    raise RuntimeError(f"candidate references unknown unit: {row['unit_id']}")
            out[(video, definition["regime"])] = rows
    return out


def safe_ranking_metrics(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float, float]:
    if len(labels) == 0 or len(set(labels.tolist())) < 2:
        return float("nan"), float("nan"), float("nan")
    return (
        float(average_precision_score(labels, scores)),
        float(roc_auc_score(labels, scores)),
        float(brier_score_loss(labels, np.clip(scores, 0.0, 1.0))),
    )


def proxy_quality_rows(
    public: dict[str, list[dict[str, Any]]],
    regimes: dict[tuple[str, str], list[dict[str, Any]]],
    labels: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    quality: list[dict[str, Any]] = []
    topk: list[dict[str, Any]] = []
    definitions = {row["regime"]: row for row in REGIMES}
    for video in VIDEOS:
        original = public[video]
        total_positive = sum(labels[row["unit_id"]].outcome == "relevant" for row in original)
        for regime in [row["regime"] for row in REGIMES]:
            rows = regimes[(video, regime)]
            binary = np.asarray([labels[row["unit_id"]].outcome == "relevant" for row in rows], dtype=int)
            scores = np.asarray([float(row["proxy_score"]) for row in rows], dtype=float)
            ap, auc, brier = safe_ranking_metrics(binary, scores)
            exposed_positive = int(binary.sum())
            quality.append({
                "video_id": video,
                "query_id": QUERY_ID,
                "regime": regime,
                "axis": definitions[regime]["axis"],
                "total_units": len(original),
                "candidate_rows": len(rows),
                "structural_candidate_exposure_recall": len(rows) / len(original),
                "total_positive_units": total_positive,
                "exposed_positive_units": exposed_positive,
                "positive_unit_recall": exposed_positive / total_positive if total_positive else float("nan"),
                "ranking_AUPRC_conditional_on_exposure": ap,
                "ranking_AUROC_conditional_on_exposure": auc,
                "uncalibrated_Brier": brier,
                "positive_prevalence_conditional": exposed_positive / len(rows),
            })
            ranked = sorted(rows, key=lambda x: (-float(x["proxy_score"]), int(x["candidate_order"]), x["candidate_id"]))
            for budget in BUDGETS:
                selected = ranked[:budget]
                positives = sum(labels[row["unit_id"]].outcome == "relevant" for row in selected)
                topk.append({
                    "video_id": video,
                    "query_id": QUERY_ID,
                    "regime": regime,
                    "budget": budget,
                    "positive_units_in_topk": positives,
                    "topk_positive_yield": positives / budget,
                    "topk_positive_recall_of_all_units": positives / total_positive if total_positive else float("nan"),
                    "topk_positive_recall_of_exposed": positives / exposed_positive if exposed_positive else float("nan"),
                })
    return quality, topk


def query_matrix(
    public: dict[str, list[dict[str, Any]]],
    regimes: dict[tuple[str, str], list[dict[str, Any]]],
    labels: dict[str, Any],
    references: dict[str, Any],
    p0: Any,
    mech: Any,
) -> list[dict[str, Any]]:
    from garc_eval.accelerated_event_query.matching import MatchConfig

    rows_out: list[dict[str, Any]] = []
    for video, regime, policy, budget in itertools.product(
        VIDEOS, [row["regime"] for row in REGIMES], POLICIES, BUDGETS
    ):
        candidates = regimes[(video, regime)]
        selected = p0.select_trace(policy, candidates, budget)
        units = [labels[row["unit_id"]] for row in selected]
        events = mech.generic_events(video, units, "C1_gap_limited")
        metrics = p0.metric_row(events, references[video], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        diagnostics = p0.diagnostics(events, references[video], units)
        trace = {
            "policy": policy,
            "video": video,
            "regime": regime,
            "queried_unit_ids": [u.unit_id for u in units],
            "outcomes": [u.outcome for u in units],
        }
        total_positive = sum(labels[row["unit_id"]].outcome == "relevant" for row in public[video])
        exposed_positive = sum(labels[row["unit_id"]].outcome == "relevant" for row in candidates)
        rows_out.append({
            "video_id": video,
            "query_id": QUERY_ID,
            "proxy_regime": regime,
            "policy": policy,
            "budget": budget,
            "materializer": "C1_gap_limited",
            "trace_hash": canonical_hash(trace),
            "queried_unit_ids_hash": canonical_hash(trace["queried_unit_ids"]),
            "oracle_outcomes_hash": canonical_hash(trace["outcomes"]),
            "oracle_calls": len(units),
            "candidate_rows": len(candidates),
            "original_units": len(public[video]),
            "structural_candidate_coverage": len(candidates) / len(public[video]),
            "positive_candidate_coverage": exposed_positive / total_positive if total_positive else float("nan"),
            "queried_fraction_of_full_universe": len(units) / len(public[video]),
            "unique_events_recovered": metrics["TP"],
            **metrics,
            **diagnostics,
        })
    return rows_out


def cumulative_auc(points: Sequence[tuple[float, float]]) -> list[float]:
    xs = [0.0] + [x for x, _ in points]
    ys = [0.0] + [y for _, y in points]
    cumulative = [0.0]
    for i in range(1, len(xs)):
        cumulative.append(cumulative[-1] + (xs[i] - xs[i - 1]) * (ys[i] + ys[i - 1]) / 2.0)
    return cumulative[1:]


def budget_analyses(frame: pd.DataFrame, protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    curve_rows: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    policy_meta = {row["name"]: row for row in protocol["policies"]}
    keys = ["video_id", "proxy_regime", "policy"]
    for key, group in frame.groupby(keys, sort=True):
        group = group.sort_values("budget")
        points = [(float(row.budget) / max(BUDGETS), float(row.F1)) for row in group.itertuples()]
        aucs = cumulative_auc(points)
        previous = None
        for i, row in enumerate(group.itertuples()):
            marginal = float("nan") if previous is None else (float(row.F1) - float(previous.F1)) / (int(row.budget) - int(previous.budget))
            curve_rows.append({
                "video_id": key[0], "proxy_regime": key[1], "policy": key[2],
                "budget": int(row.budget), "normalized_budget": int(row.budget) / max(BUDGETS),
                "F1": float(row.F1), "precision": float(row.precision), "recall": float(row.recall),
                "unique_events_recovered": int(row.unique_events_recovered),
                "marginal_F1_per_oracle_call": finite(marginal),
                "cumulative_normalized_anytime_auc": aucs[i],
                "final_normalized_anytime_auc": aucs[-1],
                "nested_budget_trace": policy_meta[key[2]]["nested_across_budget"],
            })
            if previous is not None:
                delta = float(row.F1) - float(previous.F1)
                transitions.append({
                    "video_id": key[0], "proxy_regime": key[1], "policy": key[2],
                    "budget_from": int(previous.budget), "budget_to": int(row.budget),
                    "F1_from": float(previous.F1), "F1_to": float(row.F1), "Delta_F1": delta,
                    "quality_drop": max(0.0, -delta),
                    "monotonicity_violation": delta < -EPSILON,
                    "nested_budget_trace": policy_meta[key[2]]["nested_across_budget"],
                })
            previous = row
    return curve_rows, transitions


def monotonicity_summary(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(transitions)
    rows: list[dict[str, Any]] = []
    for policy in POLICIES:
        for video in (*VIDEOS, "ALL"):
            sub = frame[frame.policy == policy]
            if video != "ALL":
                sub = sub[sub.video_id == video]
            violations = sub[sub.monotonicity_violation]
            rows.append({
                "policy": policy,
                "video_id": video,
                "transition_count": len(sub),
                "violation_count": len(violations),
                "violation_rate": len(violations) / len(sub) if len(sub) else float("nan"),
                "maximum_quality_drop": float(violations.quality_drop.max()) if len(violations) else 0.0,
                "mean_quality_drop_conditional": float(violations.quality_drop.mean()) if len(violations) else 0.0,
                "nested_budget_trace": bool(sub.nested_budget_trace.all()) if len(sub) else False,
                "primary_anytime_interpretation": policy in {"StaticProxyRank", "TemporalCoverage"},
            })
    return rows


def proxy_gap_rows(frame: pd.DataFrame, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for axis, endpoints in protocol["proxy_gap_axes"].items():
        for video, policy in itertools.product((*VIDEOS, "POOLED_MEAN"), POLICIES):
            for budget in BUDGETS:
                good = frame[(frame.proxy_regime == endpoints["good"]) & (frame.policy == policy) & (frame.budget == budget)]
                poor = frame[(frame.proxy_regime == endpoints["poor"]) & (frame.policy == policy) & (frame.budget == budget)]
                if video != "POOLED_MEAN":
                    good = good[good.video_id == video]
                    poor = poor[poor.video_id == video]
                q_good, q_poor = float(good.F1.mean()), float(poor.F1.mean())
                low_good = frame[(frame.proxy_regime == endpoints["good"]) & (frame.policy == policy) & (frame.budget == min(BUDGETS))]
                low_poor = frame[(frame.proxy_regime == endpoints["poor"]) & (frame.policy == policy) & (frame.budget == min(BUDGETS))]
                if video != "POOLED_MEAN":
                    low_good = low_good[low_good.video_id == video]
                    low_poor = low_poor[low_poor.video_id == video]
                low_gap = float(low_good.F1.mean() - low_poor.F1.mean())
                gap = q_good - q_poor
                compression = float("nan") if abs(low_gap) <= EPSILON else 1.0 - gap / low_gap
                rows.append({
                    "axis": axis, "video_id": video, "policy": policy, "budget": budget,
                    "good_regime": endpoints["good"], "poor_regime": endpoints["poor"],
                    "F1_good": q_good, "F1_poor": q_poor, "ProxyGap": gap,
                    "low_budget_gap": low_gap, "compression_relative_to_budget5": finite(compression),
                })
    return rows


def policy_effect_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for regime, budget in itertools.product([row["regime"] for row in REGIMES], BUDGETS):
        for video in (*VIDEOS, "POOLED_MEAN"):
            sub = frame[(frame.proxy_regime == regime) & (frame.budget == budget)]
            if video != "POOLED_MEAN":
                sub = sub[sub.video_id == video]
                values = {row.policy: float(row.F1) for row in sub.itertuples()}
            else:
                values = {policy: float(sub[sub.policy == policy].F1.mean()) for policy in POLICIES}
            pairwise = [abs(values[a] - values[b]) for a, b in itertools.combinations(POLICIES, 2)]
            rows.append({
                "proxy_regime": regime, "video_id": video, "budget": budget,
                **{f"F1_{policy}": values[policy] for policy in POLICIES},
                "policy_spread": max(values.values()) - min(values.values()),
                "median_abs_pairwise_policy_difference": float(np.median(pairwise)),
                "best_policy": max(values, key=lambda key: (values[key], key)),
            })
    return rows


def policy_robustness_rows(
    frame: pd.DataFrame,
    curves: list[dict[str, Any]],
    monotonicity: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    curve = pd.DataFrame(curves)
    mono = pd.DataFrame(monotonicity)
    rows: list[dict[str, Any]] = []
    poor = ("R3_RANK_SEVERE_HASH", "E3_EXPOSURE_SEVERE_KEEP040")
    for policy in POLICIES:
        means = {regime: float(frame[(frame.policy == policy) & (frame.proxy_regime == regime)].F1.mean()) for regime in [r["regime"] for r in REGIMES]}
        poor_auc = curve[(curve.policy == policy) & (curve.proxy_regime.isin(poor))].groupby(["video_id", "proxy_regime"]).final_normalized_anytime_auc.first().mean()
        mono_row = mono[(mono.policy == policy) & (mono.video_id == "ALL")].iloc[0]
        rows.append({
            "policy": policy,
            "mean_F1_all_regimes_budgets_videos": float(frame[frame.policy == policy].F1.mean()),
            "mean_F1_original": means["R0_ORIGINAL"],
            "mean_F1_rank_poor": means[poor[0]],
            "mean_F1_exposure_poor": means[poor[1]],
            "worst_poor_regime_mean_F1": min(means[poor[0]], means[poor[1]]),
            "mean_poor_regime_anytime_auc": float(poor_auc),
            "monotonicity_violation_rate": float(mono_row.violation_rate),
            "nested_budget_trace": bool(mono_row.nested_budget_trace),
        })
    order = sorted(rows, key=lambda r: (-r["worst_poor_regime_mean_F1"], -r["mean_poor_regime_anytime_auc"], r["monotonicity_violation_rate"], r["policy"]))
    rank = {row["policy"]: i + 1 for i, row in enumerate(order)}
    for row in rows:
        row["robust_policy_rank"] = rank[row["policy"]]
    return rows


def interaction_rows(
    regimes: dict[tuple[str, str], list[dict[str, Any]]], labels: dict[str, Any], references: dict[str, Any], p0: Any, mech: Any
) -> list[dict[str, Any]]:
    from garc_eval.accelerated_event_query.matching import MatchConfig

    rows: list[dict[str, Any]] = []
    for video, regime, policy, budget in itertools.product(VIDEOS, INTERACTION_REGIMES, INTERACTION_POLICIES, INTERACTION_BUDGETS):
        selected = p0.select_trace(policy, regimes[(video, regime)], budget)
        units = [labels[row["unit_id"]] for row in selected]
        c0_events = p0.k0_materialize(video, units)
        c1_events = mech.generic_events(video, units, "C1_gap_limited")
        c0 = p0.metric_row(c0_events, references[video], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        c1 = p0.metric_row(c1_events, references[video], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        rows.append({
            "video_id": video, "proxy_regime": regime, "policy": policy, "budget": budget,
            "trace_hash": canonical_hash([row["unit_id"] for row in selected]),
            "F1_C0": c0["F1"], "F1_C1": c1["F1"], "Delta_C1_minus_C0": c1["F1"] - c0["F1"],
            "TP_C0": c0["TP"], "TP_C1": c1["TP"], "FP_C0": c0["FP"], "FP_C1": c1["FP"],
        })
    return rows


def oracle_ceiling_rows(public: dict[str, list[dict[str, Any]]], labels: dict[str, Any], references: dict[str, Any], p0: Any, mech: Any) -> list[dict[str, Any]]:
    from garc_eval.accelerated_event_query.matching import MatchConfig

    rows: list[dict[str, Any]] = []
    for video, budget in itertools.product(VIDEOS, BUDGETS):
        ordered = sorted(public[video], key=lambda row: (labels[row["unit_id"]].outcome != "relevant", int(row["candidate_order"]), row["candidate_id"]))
        selected = ordered[:budget]
        units = [labels[row["unit_id"]] for row in selected]
        events = mech.generic_events(video, units, "C1_gap_limited")
        metric = p0.metric_row(events, references[video], MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
        rows.append({"video_id": video, "budget": budget, "policy": "GT_INFORMED_ORACLE_POSITIVE_RANK_CEILING", **metric})
    return rows


def bootstrap_ci(values: Sequence[float], seed: int = 20260811, n: int = 10000) -> tuple[float, float]:
    data = np.asarray(values, dtype=float)
    if not len(data):
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = np.empty(n)
    for i in range(n):
        draws[i] = np.median(rng.choice(data, size=len(data), replace=True))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def classify_results(
    protocol: dict[str, Any], matrix: pd.DataFrame, monotonicity: pd.DataFrame,
    gaps: pd.DataFrame, policy_effects: pd.DataFrame, robustness: pd.DataFrame,
    interactions: pd.DataFrame,
) -> dict[str, Any]:
    thresholds = protocol["decision_thresholds_frozen_before_results"]
    # StaticProxyRank is the only policy affected by pure ranking degradation.
    rank_pairs = []
    exposure_pairs = []
    for video in VIDEOS:
        for budget in (5, 10, 20):
            def value(regime: str, policy: str) -> float:
                return float(matrix[(matrix.video_id == video) & (matrix.proxy_regime == regime) & (matrix.policy == policy) & (matrix.budget == budget)].F1.iloc[0])
            rank_pairs.append({"video": video, "gap": value("R0_ORIGINAL", "StaticProxyRank") - value("R3_RANK_SEVERE_HASH", "StaticProxyRank")})
            for policy in POLICIES:
                exposure_pairs.append({"video": video, "gap": value("R0_ORIGINAL", policy) - value("E3_EXPOSURE_SEVERE_KEEP040", policy)})
    rank_median = float(np.median([x["gap"] for x in rank_pairs]))
    exposure_median = float(np.median([x["gap"] for x in exposure_pairs]))
    affected_videos = max(
        sum(np.median([x["gap"] for x in rank_pairs if x["video"] == video]) >= thresholds["proxy_bottleneck_partial_gap_F1"] for video in VIDEOS),
        sum(np.median([x["gap"] for x in exposure_pairs if x["video"] == video]) >= thresholds["proxy_bottleneck_partial_gap_F1"] for video in VIDEOS),
    )
    max_proxy_gap = max(rank_median, exposure_median)
    if max_proxy_gap >= thresholds["proxy_bottleneck_yes_gap_F1"] and affected_videos >= thresholds["proxy_bottleneck_cross_video_requirement"]:
        proxy_bottleneck = "YES"
    elif max_proxy_gap >= thresholds["proxy_bottleneck_partial_gap_F1"] or affected_videos >= 1:
        proxy_bottleneck = "PARTIAL"
    else:
        proxy_bottleneck = "NO"

    primary_mono = monotonicity[(monotonicity.video_id == "ALL") & monotonicity.policy.isin(["StaticProxyRank", "TemporalCoverage"])]
    violation_rate = float(primary_mono.violation_count.sum() / primary_mono.transition_count.sum())
    if violation_rate <= thresholds["resource_monotonicity_yes_max_violation_rate"]:
        resource_monotonicity = "YES"
    elif violation_rate <= thresholds["resource_monotonicity_partial_max_violation_rate"]:
        resource_monotonicity = "PARTIAL"
    else:
        resource_monotonicity = "NO"

    high = gaps[(gaps.video_id == "POOLED_MEAN") & (gaps.budget == 100)]
    compressions = [float(x) for x in high.compression_relative_to_budget5 if str(x) != "" and math.isfinite(float(x))]
    best_compression = max(compressions) if compressions else float("nan")
    if compressions and best_compression >= thresholds["gap_compression_yes"]:
        gap_compression = "YES"
    elif compressions and best_compression > thresholds["gap_compression_partial"]:
        gap_compression = "PARTIAL"
    else:
        gap_compression = "NO"

    original_effect = policy_effects[(policy_effects.proxy_regime == "R0_ORIGINAL") & (policy_effects.video_id != "POOLED_MEAN")]
    rank_poor_effect = policy_effects[(policy_effects.proxy_regime == "R3_RANK_SEVERE_HASH") & (policy_effects.video_id != "POOLED_MEAN")]
    exposure_poor_effect = policy_effects[(policy_effects.proxy_regime == "E3_EXPOSURE_SEVERE_KEEP040") & (policy_effects.video_id != "POOLED_MEAN")]
    policy_spread_good = float(np.median(original_effect.policy_spread))
    policy_spread_poor = float(np.median(pd.concat([rank_poor_effect, exposure_poor_effect]).policy_spread))
    policy_effect_all = float(np.median(policy_effects[policy_effects.video_id != "POOLED_MEAN"].policy_spread))
    policy_matters_more_poor = policy_spread_poor > policy_spread_good + thresholds["policy_matters_more_poor_margin_F1"]

    subgroup = interactions.groupby(["proxy_regime", "policy"]).Delta_C1_minus_C0.median()
    interaction_range = float(subgroup.max() - subgroup.min())
    ordering_recurrence = 0
    for video in VIDEOS:
        med = interactions[interactions.video_id == video].groupby(["proxy_regime", "policy"]).Delta_C1_minus_C0.median()
        if len(med) and (float(med.max() - med.min()) >= protocol["interaction_subset"]["systematic_interaction_threshold_F1"]):
            ordering_recurrence += 1
    systematic_interaction = interaction_range >= protocol["interaction_subset"]["systematic_interaction_threshold_F1"] and ordering_recurrence >= 2

    substantial_policy = policy_effect_all >= thresholds["policy_effect_substantial_median_spread_F1"]
    if proxy_bottleneck in {"YES", "PARTIAL"} and substantial_policy and systematic_interaction:
        mainline = "TWO_STAGE_UNIFIED"
    elif proxy_bottleneck in {"YES", "PARTIAL"} and (substantial_policy or gap_compression != "YES"):
        mainline = "QUERY_POLICY_MAINLINE"
    elif proxy_bottleneck == "NO" and not substantial_policy and thresholds["historical_materializer_effect_F1"] > policy_effect_all:
        mainline = "MATERIALIZATION_MAINLINE"
    else:
        mainline = "PIVOT_REQUIRED"

    best_robust = robustness.sort_values("robust_policy_rank").iloc[0].policy
    ci = bootstrap_ci(interactions.Delta_C1_minus_C0.tolist())
    return {
        "proxy_inaccuracy_bottleneck": proxy_bottleneck,
        "rank_degradation_low_budget_median_gap_F1": rank_median,
        "exposure_degradation_low_budget_median_gap_F1": exposure_median,
        "proxy_affected_video_count": int(affected_videos),
        "resource_monotonicity": resource_monotonicity,
        "primary_nested_monotonicity_violation_rate": violation_rate,
        "gap_compression_with_more_budget": gap_compression,
        "best_high_budget_gap_compression": finite(best_compression),
        "best_robust_policy": best_robust,
        "policy_effect_good_proxy_median_spread": policy_spread_good,
        "policy_effect_poor_proxy_median_spread": policy_spread_poor,
        "policy_effect_with_C1_fixed_median_spread": policy_effect_all,
        "policy_choice_matters_more_under_poor_proxy": "YES" if policy_matters_more_poor else "NO",
        "historical_materializer_effect_median_F1": thresholds["historical_materializer_effect_F1"],
        "selector_materializer_interaction_range": interaction_range,
        "selector_materializer_interaction_recurrent_videos": ordering_recurrence,
        "selector_materializer_interaction": "SYSTEMATIC" if systematic_interaction else "NOT_SYSTEMATIC",
        "interaction_delta_C1_C0_median": float(interactions.Delta_C1_minus_C0.median()),
        "interaction_delta_C1_C0_bootstrap_95_CI": list(ci),
        "action_selector_opportunity": "WEAK",
        "contextual_bandit_reopen": "NO",
        "project_mainline_decision": mainline,
    }


def original_thesis_text(protocol: dict[str, Any]) -> str:
    return f"""# Original GVAQP / PSVR Thesis Recovery

## Finding

Repository history repeatedly frames the project as **budgeted construction of a semantic `EventRelation` from an incomplete cheap scan plus expensive verification**, not as a standalone temporal clustering project.  Proxy imperfection, SCAN/VERIFY allocation, anytime quality, and deadline-safe visibility are first-order historical requirements.  Materialization is also explicit, but originally as the operator that converts confirmed sparse evidence into the durable query result.

This recovery predates and is not rewritten from the P0 materializer outcome.  The current audit protocol is `{protocol['protocol_hash']}`.

## Source-level chronology

| Evidence | Recovered requirement | Current interpretation |
|---|---|---|
| `configs/research_contract_v1.yaml` | Primary output `EventRelation`; actions `SCAN_FIXED`, `VERIFY_TOP1`, `STOP`; safety order includes terminal recall and anytime-recall AUC | Budget/resource conversion and durable result semantics are core contract items |
| `docs/PSVR_P0_P1_P2_EXPERIMENT_CONTRACT.md` | Proxy representations, candidate universe, event recall/F1 vs calls/deadline AUC, full-path costs | Proxy quality and resource-quality curves were formal experiment concerns |
| `configs/scan_confirm_myopic_vps.yaml` / `fixed_ratio_25_75.yaml` | Myopic SCAN/CONFIRM and fixed allocation baselines | Scan/verify allocation was an executable research axis, though seconds-based and not directly compatible with this cached matrix |
| commit `5047241b0` (2026-07-27) | Frozen partial-scan and scan-confirm results | Incomplete exposure under resource limits was already being evaluated |
| commits `dd84374c9`, `97d3412a9` (2026-07-29) | Binary SMDP evidence and ARC baseline adaptation | Adaptive/control baselines were explored; no stable mainline win followed |
| commit `735bd2f97` (2026-08-08) | Temporal-order mechanism probe | Deterministic ordering became the supported simple execution direction |
| `MAB_RESEARCH_DIRECTION_DECISION.md` | Physical-anytime, causal exposure, completion accounting; explicitly not a MAB efficacy paper | The controller research question survived, but learned-bandit claims were frozen out |
| P0 V3 and mechanism ablation | C1 fixes a large materialization failure under sparse traces | Materialization is now a supported stage, but does not erase the older proxy/budget question |

## Conflicts and limits

- Historical configs express budgets in seconds and aspire to hard deadlines; P0 and this audit use **oracle invocation counts**.  Query-budget replay cannot establish physical hard-deadline superiority.
- Historical proxy/controller studies often use Guangzhou, realcartest, dataset3, Nexar clips, older labels, or abstract costs.  They establish provenance of the thesis, not current three-video effectiveness.
- Historical `Ours`, MAB, SMDP, ECP, and fixed-ratio names do not denote one common current policy.  They are not silently promoted into the primary matrix.
- The current prospective V3 scan gives every 10-second unit a candidate.  Its original exposure is therefore complete by construction; current proxy imperfection is primarily a **ranking** question until outcome-blind thinning is introduced as stress analysis.
"""


def thesis_alignment_rows() -> list[dict[str, Any]]:
    return [
        {"research_requirement": "proxy inaccuracy", "original_importance": "HIGH", "current_implementation": "YOLOv8n midpoint proxy score; one candidate per unit", "existing_evidence": "Frozen three-video proxy tables plus this outcome-blind stress audit", "currently_resolved?": "NO", "remaining_gap": "Natural cross-model proxy regimes and real detector misses are absent", "paper_relevance": "CORE if proxy stress materially changes quality"},
        {"research_requirement": "budget scaling", "original_importance": "HIGH", "current_implementation": "Cached oracle-call budgets 5/10/20/50/80/100", "existing_evidence": "P0 and current replay", "currently_resolved?": "PARTIAL", "remaining_gap": "Query calls are not physical time", "paper_relevance": "CORE/CONTEXT depending monotonicity"},
        {"research_requirement": "resource monotonicity", "original_importance": "HIGH", "current_implementation": "Nested StaticProxyRank/TemporalCoverage prefixes; non-nested Uniform diagnostic", "existing_evidence": "Current deterministic Anytime curves", "currently_resolved?": "AUDITED_HERE", "remaining_gap": "Physical-time anytime semantics", "paper_relevance": "CORE reliability property"},
        {"research_requirement": "selector robustness", "original_importance": "HIGH", "current_implementation": "Three simple deterministic policies", "existing_evidence": "P0 selector spread and current proxy stress matrix", "currently_resolved?": "AUDITED_HERE", "remaining_gap": "No formal SUPG/ARC/ABae common-interface comparison", "paper_relevance": "CORE if poor-proxy spread is large"},
        {"research_requirement": "scan/verify allocation", "original_importance": "HIGH", "current_implementation": "Historical SCAN/VERIFY/STOP runtime; primary replay uses precomputed candidates", "existing_evidence": "Cached 108-state headroom/predictability studies", "currently_resolved?": "NO", "remaining_gap": "No current-V3 physical closed-loop multi-video evidence", "paper_relevance": "Potential core only if action opportunity is strong"},
        {"research_requirement": "materialization", "original_importance": "MEDIUM_TO_HIGH", "current_implementation": "Frozen C1 gap-only operator", "existing_evidence": "P0 54 cells; C1 median contribution about +0.1377", "currently_resolved?": "PARTIAL", "remaining_gap": "Independent human continuity still pending", "paper_relevance": "Supported operator/problem stage"},
        {"research_requirement": "hard deadline", "original_importance": "HIGH", "current_implementation": "Deadline-safe runtime exists separately", "existing_evidence": "One repeatable Guangzhou physical example; no current three-video deadline matrix", "currently_resolved?": "NO", "remaining_gap": "Cross-video physical wall-clock validation", "paper_relevance": "CONTEXT/UNPROVEN"},
        {"research_requirement": "cross-video generalization", "original_importance": "HIGH", "current_implementation": "DALI/HANGZHOU/WUHAN released reference", "existing_evidence": "P0 and current audit across three independent videos", "currently_resolved?": "PARTIAL", "remaining_gap": "Model-relative single-query scope", "paper_relevance": "Essential evidence"},
    ]


def proxy_report(quality: pd.DataFrame, topk: pd.DataFrame, protocol: dict[str, Any]) -> str:
    original = quality[quality.regime == "R0_ORIGINAL"]
    lines = []
    for row in original.itertuples():
        lines.append(
            f"| {row.video_id} | {int(row.total_units)} | {int(row.total_positive_units)} | "
            f"{row.structural_candidate_exposure_recall:.3f} | {row.positive_unit_recall:.3f} | "
            f"{row.ranking_AUPRC_conditional_on_exposure:.4f} | {row.ranking_AUROC_conditional_on_exposure:.4f} |"
        )
    return f"""# Proxy Quality Report

Protocol: `{protocol['protocol_hash']}`.  All semantic characterization was computed **after** the outcome-blind regime definitions and hashes were frozen.  No Qwen inference was run.

## Original frozen V3 proxy

| Video | Units/candidates | Positive units | Structural exposure | Positive-unit recall | Ranking AUPRC | Ranking AUROC |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(lines)}

The original V3 candidate generator emits exactly one candidate per frozen 10-second unit.  Thus both structural exposure and positive-unit exposure are `1.0` by design.  This does **not** mean the proxy is perfect: ranking quality is measured separately.  A candidate missing under the E-axis stress regimes is counted as an exposure miss and never represented as merely a low score.

## Regime interpretation

- `R0` is the only natural, current-interface proxy regime.
- `R1`–`R3` preserve the complete candidate universe and degrade only ranking through deterministic hash noise.
- `E1`–`E3` retain original scores but deterministically thin candidates, modeling exposure loss independently.
- Construction is GT-blind.  Labels are joined only for the metrics in `PROXY_QUALITY_METRICS.csv` and `PROXY_TOPK_YIELD.csv`.
- AUPRC/AUROC are conditional on exposed candidates.  `positive_unit_recall` measures exposure against all frozen semantic-positive units.  The Brier column is descriptive only because the YOLO-derived proxy score was not calibrated as a semantic probability.

## Natural-variant audit

The repository contains historical YOLO, PSVR, proxy-distillation and candidate assets, but none provides a versioned GOOD/MEDIUM/POOR set over the same DALI/HANGZHOU/WUHAN candidate universe and semantics.  They are excluded rather than forced into an unfair interface.  Consequently, causal claims must say **outcome-blind synthetic stress**, not natural proxy-model generalization.
"""


def action_opportunity_text() -> str:
    return """# Action-Selection Opportunity Audit

`ACTION_SELECTOR_OPPORTUNITY = WEAK`

`CONTEXTUAL_BANDIT_REOPEN = NO`

## Actual action space

The maintained research contract exposes `SCAN_FIXED`, `VERIFY_TOP1`, and `STOP`; current prose often calls VERIFY `CONFIRM`.  REFINE is not a first-class action in this contract.  Observable state includes elapsed/remaining fraction, scanned fraction, frontier size/top/mean score, committed-event count, and scan/verify counts.  The primary proxy stress replay does not recreate progressive SCAN: all candidate/proxy rows are precomputed, so it cannot by itself validate an adaptive SCAN/VERIFY controller.

## Existing counterfactual evidence

- The cached 108-state headroom audit found heterogeneous realized action values: 25 `SCAN_BETTER`, 26 `VERIFY_BETTER`, 57 tied, with both directions on two source videos.  This is evidence that state-dependent value can exist.
- The corresponding public-state predictability audit failed its gate.  Best fixed `always_verify` regret was `0.000885`; the best learned linear rule had regret `0.009693` (10.95× worse), and the contextual-bandit control had regret `0.010325`.
- Those audits use two sources, older query/reference assets and abstract costs rather than current V3 physical time.  The older PSVR bottleneck program also ended `COMPLETE_NO_GO`, with no cross-video scan/verify quality signal.

## Decision

The evidence meets neither requirement for `STRONG`: observable-state-dependent best actions exist in a diagnostic replay, but simple fixed-policy regret is tiny and learned/public-state decisions do not exploit the heterogeneity.  Therefore MAB remains `ARCHIVED_NON_MAINLINE`.  A theory-level fit to a bandit/SMDP is not empirical justification to reopen it.
"""


def interaction_report(interactions: pd.DataFrame, result: dict[str, Any]) -> str:
    med = interactions.groupby(["proxy_regime", "policy"]).Delta_C1_minus_C0.median().reset_index()
    table = "\n".join(f"| {r.proxy_regime} | {r.policy} | {r.Delta_C1_minus_C0:.4f} |" for r in med.itertuples())
    return f"""# Selector × Materializer Interaction Audit

This secondary replay was frozen to 3 regimes × 2 policies × 3 budgets × 3 videos before results.  K0 and C1 consume identical traces; it does not retune C1 or rerun the full primary matrix.

| Proxy regime | Policy | Median ΔF1 (C1−C0) |
|---|---|---:|
{table}

- Cross-subgroup median range: `{result['selector_materializer_interaction_range']:.4f}`.
- Videos with at least the frozen `0.05` subgroup range: `{result['selector_materializer_interaction_recurrent_videos']} / 3`.
- Frozen decision: `{result['selector_materializer_interaction']}`.

An interaction here means the **size** of C1's correction depends on which sparse trace the proxy/policy creates; it does not mean either stage changes the other's implementation.  The reference remains full-grid K3-defined, so this is model-relative mechanism evidence.
"""


def mainline_scorecard(result: dict[str, Any]) -> list[dict[str, Any]]:
    decision = result["project_mainline_decision"]
    return [
        {"route": "QUERY_POLICY", "alignment_with_original_problem": "HIGH", "empirical_support": "MEDIUM" if result["proxy_inaccuracy_bottleneck"] != "NO" else "LOW", "novelty": "MEDIUM", "generality": "MEDIUM", "database_relevance": "HIGH", "technical_depth": "MEDIUM", "remaining_work": "HIGH", "reviewer_risk": "HIGH: synthetic proxy stress and query-count budget", "selected": decision == "QUERY_POLICY_MAINLINE"},
        {"route": "MATERIALIZATION", "alignment_with_original_problem": "MEDIUM", "empirical_support": "HIGH_MODEL_RELATIVE / WEAK_INDEPENDENT_SEMANTIC", "novelty": "LOW_MECHANISM / MEDIUM_OPERATOR_FRAMING", "generality": "MEDIUM", "database_relevance": "HIGH if framed as EventRelation construction", "technical_depth": "LOW_TO_MEDIUM", "remaining_work": "HUMAN_VALIDATION", "reviewer_risk": "HIGH: K3-defined reference and simple sessionization", "selected": decision == "MATERIALIZATION_MAINLINE"},
        {"route": "TWO_STAGE", "alignment_with_original_problem": "HIGH", "empirical_support": "MEDIUM_TO_HIGH" if decision == "TWO_STAGE_UNIFIED" else "MEDIUM", "novelty": "MEDIUM operator separation", "generality": "MEDIUM", "database_relevance": "HIGH", "technical_depth": "MEDIUM", "remaining_work": "HIGH", "reviewer_risk": "HIGH: thesis breadth can obscure primary novelty", "selected": decision == "TWO_STAGE_UNIFIED"},
    ]


def decision_text(result: dict[str, Any], robustness: pd.DataFrame) -> str:
    role = {
        "QUERY_POLICY_MAINLINE": ("SUPPORTING", "CORE"),
        "MATERIALIZATION_MAINLINE": ("CORE", "SUPPORTING"),
        "TWO_STAGE_UNIFIED": ("CORE_STAGE", "CORE_STAGE"),
        "PIVOT_REQUIRED": ("SUPPORTING_ONLY", "SUPPORTING_ONLY"),
    }[result["project_mainline_decision"]]
    thesis = {
        "QUERY_POLICY_MAINLINE": "Robust budgeted event-query execution must convert imperfect cheap evidence into progressively improving semantic event recovery; C1 is the fixed result operator.",
        "MATERIALIZATION_MAINLINE": "Sparse semantic verification creates an EventRelation materialization problem whose current effect exceeds proxy/policy variation; C1 is the minimal mechanism.",
        "TWO_STAGE_UNIFIED": "Robust sparse event-query execution requires both evidence acquisition under imperfect proxy and explicit EventRelation materialization, with the primary algorithmic gap remaining query-policy robustness.",
        "PIVOT_REQUIRED": "Neither the current proxy-policy layer nor independently validated materialization evidence is strong enough to support the present thesis.",
    }[result["project_mainline_decision"]]
    return f"""# GVAQP Main-Thesis Decision

`PROJECT_MAINLINE_DECISION = {result['project_mainline_decision']}`

## Answers to the five primary questions

1. `IS PROXY INACCURACY A FIRST-ORDER QUALITY BOTTLENECK? {result['proxy_inaccuracy_bottleneck']}`  Ranking-stress median low-budget gap is `{result['rank_degradation_low_budget_median_gap_F1']:.4f}`; exposure-stress median is `{result['exposure_degradation_low_budget_median_gap_F1']:.4f}`.
2. `DOES MORE RESOURCE RELIABLY IMPROVE QUALITY? {result['resource_monotonicity']}`  Nested-policy violation rate is `{result['primary_nested_monotonicity_violation_rate']:.2%}`.
3. `CAN CURRENT POLICIES COMPRESS THE POOR-vs-GOOD PROXY GAP? {result['gap_compression_with_more_budget']}`  Best descriptive high-budget compression is `{result['best_high_budget_gap_compression']}`.
4. `DOES POLICY CHOICE MATTER MORE UNDER POOR PROXY? {result['policy_choice_matters_more_under_poor_proxy']}`  Median spread good=`{result['policy_effect_good_proxy_median_spread']:.4f}`, poor=`{result['policy_effect_poor_proxy_median_spread']:.4f}`.
5. With C1 fixed, median three-policy spread is `{result['policy_effect_with_C1_fixed_median_spread']:.4f}`, versus historical model-relative materializer median `0.1457`.

## Thesis

{thesis}

- Materialization role: `{role[0]}`.
- Query-policy role: `{role[1]}`.
- Deadline role: `CONTEXT / UNPROVEN`; all primary numbers are query-count replay.
- Best robust current policy: `{result['best_robust_policy']}` under the frozen lexicographic worst-proxy rule.
- Selector × materializer interaction: `{result['selector_materializer_interaction']}`.
- Action selector opportunity: `WEAK`; contextual bandit reopen: `NO`.

## Claim boundary

The audit supports only deterministic, model-relative, outcome-blind proxy-stress claims over three videos and one query.  It does not establish robustness across natural proxy models, human semantic correctness, learned-controller benefit, or hard-deadline superiority.
"""


def final_report(
    protocol: dict[str, Any], result: dict[str, Any], matrix: pd.DataFrame, quality: pd.DataFrame,
    curves: pd.DataFrame, gaps: pd.DataFrame, effects: pd.DataFrame, robustness: pd.DataFrame,
) -> str:
    per_video = []
    for video in VIDEOS:
        original = matrix[(matrix.video_id == video) & (matrix.proxy_regime == "R0_ORIGINAL")]
        rank_poor = matrix[(matrix.video_id == video) & (matrix.proxy_regime == "R3_RANK_SEVERE_HASH")]
        exposure_poor = matrix[(matrix.video_id == video) & (matrix.proxy_regime == "E3_EXPOSURE_SEVERE_KEEP040")]
        per_video.append(f"| {video} | {original.F1.mean():.4f} | {rank_poor.F1.mean():.4f} | {exposure_poor.F1.mean():.4f} |")
    robust_table = "\n".join(
        f"| {r.policy} | {r.worst_poor_regime_mean_F1:.4f} | {r.mean_poor_regime_anytime_auc:.4f} | {r.monotonicity_violation_rate:.2%} | {int(r.robust_policy_rank)} |"
        for r in robustness.sort_values("robust_policy_rank").itertuples()
    )
    return f"""# GVAQP Main-Thesis Alignment & Proxy-Robust Query Execution Audit

## Executive decision

`PROJECT_MAINLINE_DECISION = {result['project_mainline_decision']}`

The historical core question is budgeted construction of a semantic `EventRelation` when cheap evidence is incomplete or inaccurate.  This audit fixes the supported C1 gap-only materializer and tests proxy ranking, exposure, policy, and oracle-call budget without new semantic inference.

## Experimental contract

- Protocol `{protocol['protocol_hash']}` was frozen before any new proxy-stress Event-F1 was computed.
- Three independent videos: DALI, HANGZHOU, WUHAN; one frozen model-relative query/reference.
- Seven regimes: one natural prospective V3 proxy, three outcome-blind ranking degradations, three outcome-blind exposure degradations.
- Policies: UniformTemporal, StaticProxyRank, TemporalCoverage; budgets: 5/10/20/50/80/100 oracle calls.
- Materializer: C1, gap ≤10 seconds, no duration cap, negative barrier, or K3 extras.
- Semantic oracle calls: zero.  These are cached `QUERY_BUDGET` results, not wall-clock deadlines.

## Current proxy characterization

Original candidate exposure is 100% because every V3 unit becomes a candidate.  Ranking AUPRC by video is: {', '.join(f"{r.video_id}={r.ranking_AUPRC_conditional_on_exposure:.4f}" for r in quality[quality.regime == 'R0_ORIGINAL'].itertuples())}.  Therefore original exposure quality is structurally maximal while ranking quality is empirical and video-dependent.

## Proxy and policy results

- Proxy inaccuracy bottleneck: `{result['proxy_inaccuracy_bottleneck']}`.
- Ranking severe-vs-original low-budget median gap: `{result['rank_degradation_low_budget_median_gap_F1']:.4f}`.
- Exposure severe-vs-original low-budget median gap: `{result['exposure_degradation_low_budget_median_gap_F1']:.4f}`.
- Policy median spread under original proxy: `{result['policy_effect_good_proxy_median_spread']:.4f}`.
- Policy median spread under poor regimes: `{result['policy_effect_poor_proxy_median_spread']:.4f}`.
- Policy effect with C1 fixed over all regimes: `{result['policy_effect_with_C1_fixed_median_spread']:.4f}`.

| Video | Mean F1 original | Mean F1 rank-severe | Mean F1 exposure-severe |
|---|---:|---:|---:|
{chr(10).join(per_video)}

## Resource monotonicity and anytime quality

For nested StaticProxyRank and TemporalCoverage traces, monotonicity is `{result['resource_monotonicity']}` with `{result['primary_nested_monotonicity_violation_rate']:.2%}` transition violations.  UniformTemporal exact subsets are non-nested and excluded from the primary anytime reliability judgment.  `ANYTIME_BUDGET_CURVES.csv` contains normalized trapezoidal AUC from `(0,0)` plus marginal F1/oracle-call values.

More oracle calls can expose additional positives but can also add false events under a precision-sensitive event metric.  A violation is thus a genuine query-result reliability finding, not floating noise (epsilon `{EPSILON}`).

## Poor-vs-good gap compression

Current policies compress the gap: `{result['gap_compression_with_more_budget']}`.  The best high-budget descriptive compression is `{result['best_high_budget_gap_compression']}`; undefined ratios remain blank when the budget-5 denominator is zero.  Ranking and exposure gaps are reported separately in `PROXY_GAP_COMPRESSION.csv`.

## Robust-policy comparison

| Policy | Worst poor-regime mean F1 | Poor-regime Anytime AUC | Monotonic violations | Robust rank |
|---|---:|---:|---:|---:|
{robust_table}

The robust rank is not best-point cherry-picking: it follows the pre-frozen lexicographic rule (worst poor-regime F1, poor Anytime AUC, then monotonicity).

## Materialization comparison and interaction

Historical model-relative median K3−K0 is `+0.1457`; mechanism ablation attributes about `+0.1377` to C1.  With C1 fixed, current policy spread is `{result['policy_effect_with_C1_fixed_median_spread']:.4f}`.  The representative same-trace C0/C1 subset yields interaction `{result['selector_materializer_interaction']}` with subgroup range `{result['selector_materializer_interaction_range']:.4f}`.  This determines whether the stages can be treated as nearly separable in the paper.

## Adaptive action-selection opportunity

`ACTION_SELECTOR_OPPORTUNITY = WEAK`; `CONTEXTUAL_BANDIT_REOPEN = NO`.  Cached counterfactuals contain both SCAN-better and VERIFY-better states, but observable-state learned rules have more regret than a tiny-regret fixed always-VERIFY policy.  The current precomputed-candidate replay does not test progressive SCAN/VERIFY control.

## Mainline interpretation

The selected route is `{result['project_mainline_decision']}`.  Full K3 remains unsupported as the core algorithm; C1 is the frozen supported materialization operator.  Deadline awareness remains contextual because the current quality curves are invocation-budget curves.

## Evidence limitations and conflicts

1. Proxy degradations are prospective, deterministic and outcome-blind, but synthetic; no natural three-regime proxy family exists on this current interface.
2. The reference is Qwen model-relative and K3-grouped.  Independent human continuity remains pending; SmolVLM evidence remains inconclusive.
3. One candidate per unit makes original exposure recall trivially 100%; this design tests ranking, while thinning is only a stress model of exposure loss.
4. UniformTemporal is non-nested across budgets; its curves must not be called strict anytime execution.
5. Historical controller results use different videos/references and abstract or physical costs; they support thesis provenance, not the current primary matrix.
6. The P0 report's broad anti-overmerge language is stronger than its causal mechanism ablation: duration-cap and queried-negative-barrier marginal medians are zero; gap-only C1 carries the demonstrated median gain.

## Single next experiment

Run one preregistered **natural-proxy replication** on the same frozen three-video/unit interface using a second maintained cheap visual proxy, without tuning on semantic labels.  It is the single experiment that can distinguish robust query-policy evidence from artifacts of synthetic corruption while preserving C1 and the evaluation contract.
"""


def run() -> None:
    protocol = load_protocol()
    p0 = p0_module()
    mech = mechanism_module()
    labels, _, references = p0.load_data()
    public = load_candidate_proxy_only()
    regimes = enrich_candidates(public, labels)

    quality_rows, topk_rows = proxy_quality_rows(public, regimes, labels)
    matrix_rows = query_matrix(public, regimes, labels, references, p0, mech)
    matrix = pd.DataFrame(matrix_rows)
    curve_rows, transition_rows = budget_analyses(matrix, protocol)
    monotonicity_rows = monotonicity_summary(transition_rows)
    gap_rows = proxy_gap_rows(matrix, protocol)
    effect_rows = policy_effect_rows(matrix)
    robustness_rows = policy_robustness_rows(matrix, curve_rows, monotonicity_rows)
    interaction_data = interaction_rows(regimes, labels, references, p0, mech)
    ceiling_rows = oracle_ceiling_rows(public, labels, references, p0, mech)

    quality = pd.DataFrame(quality_rows)
    curves = pd.DataFrame(curve_rows)
    monotonicity = pd.DataFrame(monotonicity_rows)
    gaps = pd.DataFrame(gap_rows)
    effects = pd.DataFrame(effect_rows)
    robustness = pd.DataFrame(robustness_rows)
    interactions = pd.DataFrame(interaction_data)
    result = classify_results(protocol, matrix, monotonicity, gaps, effects, robustness, interactions)

    write_csv_once(OUT / "PROXY_QUALITY_METRICS.csv", quality_rows)
    write_csv_once(OUT / "PROXY_TOPK_YIELD.csv", topk_rows)
    write_csv_once(OUT / "QUERY_POLICY_MATRIX.csv", matrix_rows)
    write_csv_once(OUT / "ANYTIME_BUDGET_CURVES.csv", curve_rows)
    write_csv_once(OUT / "RESOURCE_MONOTONICITY_TRANSITIONS.csv", transition_rows)
    write_csv_once(OUT / "RESOURCE_MONOTONICITY.csv", monotonicity_rows)
    write_csv_once(OUT / "PROXY_GAP_COMPRESSION.csv", gap_rows)
    write_csv_once(OUT / "POLICY_EFFECT_BY_PROXY.csv", effect_rows)
    write_csv_once(OUT / "POLICY_ROBUSTNESS.csv", robustness_rows)
    write_csv_once(OUT / "SELECTOR_MATERIALIZER_INTERACTION.csv", interaction_data)
    write_csv_once(OUT / "ORACLE_DIAGNOSTIC_CEILING.csv", ceiling_rows)
    write_json_once(OUT / "RESULT_SUMMARY.json", result)

    write_text_once(OUT / "ORIGINAL_THESIS_RECOVERY.md", original_thesis_text(protocol))
    write_csv_once(OUT / "THESIS_ALIGNMENT_MATRIX.csv", thesis_alignment_rows())
    write_text_once(OUT / "PROXY_QUALITY_REPORT.md", proxy_report(quality, pd.DataFrame(topk_rows), protocol))
    write_text_once(OUT / "ACTION_SELECTION_OPPORTUNITY.md", action_opportunity_text())
    write_text_once(OUT / "SELECTOR_MATERIALIZER_INTERACTION.md", interaction_report(interactions, result))
    write_csv_once(OUT / "MAINLINE_SCORECARD.csv", mainline_scorecard(result))
    write_text_once(OUT / "MAIN_THESIS_DECISION.md", decision_text(result, robustness))
    write_text_once(OUT / "FINAL_ALIGNMENT_REPORT.md", final_report(protocol, result, matrix, quality, curves, gaps, effects, robustness))
    write_json_once(OUT / "AUDIT_COMPLETION_MANIFEST.json", {
        "status": "COMPLETE",
        "protocol_hash": protocol["protocol_hash"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "semantic_oracle_calls": 0,
        "primary_matrix_cells": len(matrix),
        "project_mainline_decision": result["project_mainline_decision"],
        "output_hashes": {
            path.name: sha256_file(path)
            for path in sorted(OUT.iterdir())
            if path.is_file() and path.name != "AUDIT_COMPLETION_MANIFEST.json"
        },
    })
    print(json.dumps({"status": "COMPLETE", "protocol_hash": protocol["protocol_hash"], **result}, indent=2))


def self_test() -> None:
    ids = ["DALI::DALI_u0000", "DALI::DALI_u0001", "DALI::DALI_u0002"]
    first = [deterministic_uniform(x, "R3_RANK_SEVERE_HASH", "ranking") for x in ids]
    second = [deterministic_uniform(x, "R3_RANK_SEVERE_HASH", "ranking") for x in ids]
    assert first == second and len(set(first)) == len(first)
    assert all(0.0 <= x < 1.0 for x in first)
    dummy = [{"candidate_id": ids[i], "candidate_order": i, "proxy_score": i / 2, "source_unit_ids": [f"u{i}"]} for i in range(3)]
    severe = construct_regime(dummy, next(x for x in REGIMES if x["regime"] == "R3_RANK_SEVERE_HASH"))
    assert len(severe) == 3 and [x["proxy_score"] for x in severe] == first
    assert set(BUDGETS) == {5, 10, 20, 50, 80, 100}
    assert len(REGIMES) == 7 and set(POLICIES) == {"UniformTemporal", "StaticProxyRank", "TemporalCoverage"}
    print(json.dumps({"status": "SELF_TEST_PASS", "hash_values": first}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["self-test", "freeze", "run"])
    args = parser.parse_args()
    if args.action == "self-test":
        self_test()
    elif args.action == "freeze":
        freeze()
    else:
        run()


if __name__ == "__main__":
    main()
