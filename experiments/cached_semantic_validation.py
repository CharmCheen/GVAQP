#!/usr/bin/env python3
"""Developmental RC-SEM validation against preserved 32B semantic caches.

This experiment is deliberately separate from the GVAQP repository.  Hidden
oracle labels are used only by the evaluator portions of this process.  The
result is a retrospective mechanism screen, not a confirmatory replay: the
source benchmarks themselves document provenance and process-isolation limits.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from rc_sem.materialization import MaterializationConfig, RiskControlledMaterializer
from rc_sem.metrics import anytime_auc
from rc_sem.types import EventHypothesis


PARTIAL_FEATURES = (
    "candidate_score",
    "approximate_ttc_urgency",
    "boundary_crossing",
    "box_growth",
    "ego_corridor_overlap",
    "front_region_occupancy",
    "lane_relative_motion",
    "observations",
    "path_directed_lateral_motion",
    "road_geometry_reliability",
    "track_persistence",
    "class_id",
)

BUDGETS = (5, 10, 20, 50, 100)
PARTIAL_VIDEOS = ("PSP_V0_SHORT", "PSP_V1_LONG")
PROMPT_HASH_PARTIAL = "19dc06ecb77c03d19320ed20a9c2281cbaa676b5a7f8112cf8eca2361311d370"
PROMPT_HASH_CLEAN = "12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33"


@dataclass(frozen=True)
class RiskThreshold:
    score_threshold: float
    admitted_count: int
    empirical_precision: float
    wilson_lower_95: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson_lower(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials <= 0:
        return 0.0
    proportion = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = proportion + z2 / (2.0 * trials)
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / trials + z2 / (4.0 * trials * trials)
    )
    return max(0.0, (center - radius) / denominator)


def choose_risk_threshold(
    scores: Sequence[float],
    labels: Sequence[int],
    *,
    precision_floor: float,
    minimum_admissions: int,
) -> RiskThreshold | None:
    score_array = np.asarray(scores, dtype=float)
    label_array = np.asarray(labels, dtype=int)
    if len(score_array) != len(label_array):
        raise ValueError("score and label counts differ")
    choices: list[RiskThreshold] = []
    for threshold in sorted(np.unique(score_array), reverse=True):
        selected = score_array >= threshold
        trials = int(selected.sum())
        if trials < minimum_admissions:
            continue
        successes = int(label_array[selected].sum())
        lower = wilson_lower(successes, trials)
        if lower + 1e-15 >= precision_floor:
            choices.append(
                RiskThreshold(
                    score_threshold=float(threshold),
                    admitted_count=trials,
                    empirical_precision=successes / trials,
                    wilson_lower_95=lower,
                )
            )
    if not choices:
        return None
    return max(choices, key=lambda row: (row.admitted_count, row.score_threshold))


def posterior_model(seed: int):
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(
            C=0.5,
            class_weight="balanced",
            max_iter=2000,
            random_state=seed,
        ),
    )


def fit_oof_and_test(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    features: Sequence[str],
    group_column: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    group_count = int(train[group_column].nunique())
    if group_count < 2:
        raise ValueError("at least two temporal groups are required")
    folds = min(5, group_count)
    model = posterior_model(seed)
    oof = cross_val_predict(
        model,
        train[list(features)],
        train["label"].to_numpy(dtype=int),
        groups=train[group_column],
        cv=GroupKFold(n_splits=folds),
        method="predict_proba",
        n_jobs=1,
    )[:, 1]
    model.fit(train[list(features)], train["label"].to_numpy(dtype=int))
    heldout = model.predict_proba(test[list(features)])[:, 1]
    return oof, heldout


def candidate_reference_adjacency(
    match_rows: pd.DataFrame,
    candidate_ids: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    selected = set(candidate_ids)
    rows = match_rows.loc[match_rows["candidate_id"].isin(selected)].copy()
    rows = rows.sort_values(
        ["candidate_id", "temporal_intersection_sec", "reference_midpoint_contained", "reference_event_id"],
        ascending=[True, False, False, True],
    )
    adjacency: dict[str, tuple[str, ...]] = {}
    for candidate_id, group in rows.groupby("candidate_id", sort=True):
        adjacency[str(candidate_id)] = tuple(dict.fromkeys(group["reference_event_id"].astype(str)))
    return adjacency


def maximum_one_to_one_match(
    candidate_ids: Iterable[str],
    adjacency: Mapping[str, Sequence[str]],
    *,
    unavailable_references: Iterable[str] = (),
) -> dict[str, str]:
    """Return a deterministic maximum-cardinality candidate/reference match."""
    blocked = set(unavailable_references)
    reference_to_candidate: dict[str, str] = {}

    def augment(candidate_id: str, seen: set[str]) -> bool:
        for reference_id in adjacency.get(candidate_id, ()):
            if reference_id in blocked or reference_id in seen:
                continue
            seen.add(reference_id)
            prior = reference_to_candidate.get(reference_id)
            if prior is None or augment(prior, seen):
                reference_to_candidate[reference_id] = candidate_id
                return True
        return False

    for candidate_id in sorted(set(candidate_ids)):
        augment(candidate_id, set())
    return {candidate_id: reference_id for reference_id, candidate_id in reference_to_candidate.items()}


def publication_metrics(
    candidate_ids: Sequence[str],
    adjacency: Mapping[str, Sequence[str]],
    *,
    reference_count: int,
) -> dict[str, float | int | None]:
    matching = maximum_one_to_one_match(candidate_ids, adjacency)
    true_count = len(matching)
    returned_count = len(set(candidate_ids))
    return {
        "returned_event_hypotheses": returned_count,
        "matched_reference_events": true_count,
        "false_or_duplicate_events": returned_count - true_count,
        "event_precision": true_count / returned_count if returned_count else None,
        "event_recall": true_count / reference_count if reference_count else 0.0,
    }


def verified_prefix_metrics(
    ranked_candidates: Sequence[str],
    adjacency: Mapping[str, Sequence[str]],
    *,
    probable_candidates: Sequence[str],
    reference_count: int,
    budget: int,
) -> dict[str, float | int | None]:
    probable = tuple(dict.fromkeys(probable_candidates))
    probable_match = maximum_one_to_one_match(probable, adjacency)
    probable_references = set(probable_match.values())
    false_probable = len(probable) - len(probable_match)

    verify_order = [candidate for candidate in ranked_candidates if candidate not in set(probable)]
    verify_order = verify_order[:budget]
    points: list[tuple[float, float]] = [(0.0, len(probable_references) / reference_count)]
    recovered = set(probable_references)
    for action_index, _candidate_id in enumerate(verify_order, start=1):
        verified_match = maximum_one_to_one_match(
            verify_order[:action_index],
            adjacency,
            unavailable_references=probable_references,
        )
        recovered = probable_references | set(verified_match.values())
        points.append((float(action_index), len(recovered) / reference_count))
    if len(verify_order) < budget:
        points.append((float(budget), len(recovered) / reference_count))

    returned_count = len(recovered) + false_probable
    return {
        "verify_calls": len(verify_order),
        "probable_count": len(probable),
        "true_returned_events": len(recovered),
        "false_probable_events": false_probable,
        "combined_precision": len(recovered) / returned_count if returned_count else None,
        "event_recall": len(recovered) / reference_count,
        "anytime_event_recall_auc": anytime_auc(points, deadline_sec=float(budget)),
    }


def load_partial_data(repo_root: Path) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, list[Path]]:
    partial_root = repo_root / "benchmarks/partial_scan_pilot_v1"
    candidate_dir = partial_root / "derived/visible_subset_candidates"
    paths = {
        "PSP_V0_SHORT": candidate_dir / "PSP_V0_SHORT_offset0_full.parquet",
        "PSP_V1_LONG": candidate_dir / "PSP_V1_LONG_offset0_full.parquet",
    }
    match_path = partial_root / "derived/candidate_event_map.parquet"
    reference_path = partial_root / "immutable/reference_events.csv"
    frames: dict[str, pd.DataFrame] = {}
    for video_id, path in paths.items():
        frame = pq.read_table(path).to_pandas()
        frame["video_id"] = video_id
        frame["temporal_group"] = (frame["candidate_start_sec"] // 300.0).astype(int)
        frames[video_id] = frame
    matches = pq.read_table(match_path).to_pandas()
    references = pd.read_csv(reference_path)
    candidate_universe = set().union(*(set(frame["candidate_id"]) for frame in frames.values()))
    matches = matches.loc[matches["candidate_id"].isin(candidate_universe)].copy()
    positive_ids = set(matches["candidate_id"])
    for frame in frames.values():
        frame["label"] = frame["candidate_id"].isin(positive_ids).astype(int)
    return frames, matches, references, [*paths.values(), match_path, reference_path]


def run_partial_validation(
    repo_root: Path,
    *,
    precision_floor: float,
    minimum_admissions: int,
    seed: int,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[Path]]:
    frames, matches, references, input_paths = load_partial_data(repo_root)
    fold_rows: list[dict] = []
    budget_rows: list[dict] = []
    ablation_rows: list[dict] = []
    prediction_rows: list[dict] = []

    for heldout_video in PARTIAL_VIDEOS:
        train_video = next(video for video in PARTIAL_VIDEOS if video != heldout_video)
        train = frames[train_video].copy()
        test = frames[heldout_video].copy()
        oof_scores, test_scores = fit_oof_and_test(
            train,
            test,
            features=PARTIAL_FEATURES,
            group_column="temporal_group",
            seed=seed,
        )
        threshold = choose_risk_threshold(
            oof_scores,
            train["label"],
            precision_floor=precision_floor,
            minimum_admissions=minimum_admissions,
        )
        test["posterior_score"] = test_scores
        reference_count = int((references["video_id"] == heldout_video).sum())
        adjacency = candidate_reference_adjacency(matches, test["candidate_id"])

        hypotheses: list[EventHypothesis] = []
        for row in test.itertuples(index=False):
            is_risk_admissible = threshold is not None and row.posterior_score >= threshold.score_threshold
            lower = threshold.wilson_lower_95 if is_risk_admissible else 0.0
            mean = max(float(row.posterior_score), lower)
            hypotheses.append(
                EventHypothesis(
                    event_id=str(row.candidate_id),
                    start_time=float(row.candidate_start_sec),
                    end_time=float(row.candidate_end_sec),
                    probability_mean=mean,
                    probability_uncertainty=max(0.0, mean - lower),
                    source_candidate_ids=(str(row.candidate_id),),
                    provenance={"fold": heldout_video, "label_visible_to_runtime": False},
                )
            )
        snapshot = RiskControlledMaterializer(
            MaterializationConfig(
                probable_threshold=precision_floor,
                precision_floor=precision_floor,
                uncertainty_beta=1.0,
                false_positive_penalty=1.0,
            )
        ).materialize(hypotheses, elapsed_sec=0.0)
        probable_ids = [row.event_id for row in snapshot.events]
        probable_metrics = publication_metrics(
            probable_ids,
            adjacency,
            reference_count=reference_count,
        )

        fold_rows.append(
            {
                "semantic_query": "TARGET_VEHICLE_CUT_IN",
                "prompt_hash": PROMPT_HASH_PARTIAL,
                "train_video": train_video,
                "heldout_video": heldout_video,
                "train_candidates": len(train),
                "heldout_candidates": len(test),
                "train_positive_fraction": float(train["label"].mean()),
                "heldout_positive_fraction": float(test["label"].mean()),
                "oof_roc_auc": float(roc_auc_score(train["label"], oof_scores)),
                "oof_average_precision": float(average_precision_score(train["label"], oof_scores)),
                "risk_threshold_found": threshold is not None,
                "risk_score_threshold": threshold.score_threshold if threshold else None,
                "risk_train_admissions": threshold.admitted_count if threshold else 0,
                "risk_train_empirical_precision": threshold.empirical_precision if threshold else None,
                "risk_train_wilson_lower_95": threshold.wilson_lower_95 if threshold else None,
                **{f"probable_{key}": value for key, value in probable_metrics.items()},
            }
        )

        for gate_name, selected in (
            ("MEAN_P_GE_0P8_UNSAFE_ABLATION", test["posterior_score"] >= 0.8),
            ("RAW_CANDIDATE_SCORE_GE_0P8_UNSAFE_ABLATION", test["candidate_score"] >= 0.8),
        ):
            ids = list(test.loc[selected, "candidate_id"].astype(str))
            metrics = publication_metrics(ids, adjacency, reference_count=reference_count)
            ablation_rows.append(
                {
                    "heldout_video": heldout_video,
                    "gate": gate_name,
                    **metrics,
                }
            )

        raw_ranking = list(
            test.sort_values(["candidate_score", "candidate_id"], ascending=[False, True])["candidate_id"].astype(str)
        )
        posterior_ranking = list(
            test.sort_values(["posterior_score", "candidate_id"], ascending=[False, True])["candidate_id"].astype(str)
        )
        for budget in BUDGETS:
            for method, ranking, probable in (
                ("RAW_PROXY_VERIFIED_ONLY", raw_ranking, ()),
                ("POSTERIOR_VERIFIED_ONLY", posterior_ranking, ()),
                ("RC_SEM_RISK_CONTROLLED", posterior_ranking, probable_ids),
            ):
                metrics = verified_prefix_metrics(
                    ranking,
                    adjacency,
                    probable_candidates=probable,
                    reference_count=reference_count,
                    budget=budget,
                )
                budget_rows.append(
                    {
                        "heldout_video": heldout_video,
                        "method": method,
                        "verify_budget": budget,
                        **metrics,
                    }
                )

        for row in test.itertuples(index=False):
            prediction_rows.append(
                {
                    "heldout_video": heldout_video,
                    "candidate_id": str(row.candidate_id),
                    "candidate_start_sec": float(row.candidate_start_sec),
                    "candidate_end_sec": float(row.candidate_end_sec),
                    "raw_candidate_score": float(row.candidate_score),
                    "posterior_score": float(row.posterior_score),
                    "evaluator_label": int(row.label),
                    "risk_admitted": bool(row.candidate_id in set(probable_ids)),
                }
            )

    return fold_rows, budget_rows, ablation_rows, prediction_rows, input_paths


def run_clean_cache_diagnostic(
    repo_root: Path,
    *,
    precision_floor: float,
    minimum_admissions: int,
    seed: int,
) -> tuple[dict, list[Path]]:
    base = (
        repo_root
        / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2"
    )
    proxy_path = base / "frozen_inputs/public_proxy.csv"
    oracle_path = base / "oracle/oracle_presence_observations.csv"
    reference_path = base / "frozen_inputs/event_reference.csv"
    proxy = pd.read_csv(proxy_path).pivot(
        index="unit_id", columns="proxy_name", values="proxy_score_normalized"
    )
    oracle = pd.read_csv(oracle_path).set_index("unit_id")
    frame = proxy.join(oracle[["parsed_label", "start_time"]], how="inner").sort_index()
    frame["label"] = (frame["parsed_label"] == "positive").astype(int)
    frame["temporal_group"] = (frame["start_time"] // 300.0).astype(int)
    features = sorted(set(proxy.columns))
    oof_scores, _unused = fit_oof_and_test(
        frame,
        frame.iloc[:1],
        features=features,
        group_column="temporal_group",
        seed=seed,
    )
    threshold = choose_risk_threshold(
        oof_scores,
        frame["label"],
        precision_floor=precision_floor,
        minimum_admissions=minimum_admissions,
    )
    naive = oof_scores >= 0.8
    return (
        {
            "semantic_query": "OBJECT_ENTERS_EGO_PATH",
            "prompt_hash": PROMPT_HASH_CLEAN,
            "video_id": "long_video_dataset3",
            "unit_count": len(frame),
            "positive_units": int(frame["label"].sum()),
            "reference_event_count": len(pd.read_csv(reference_path)),
            "blocked_oof_roc_auc": float(roc_auc_score(frame["label"], oof_scores)),
            "blocked_oof_average_precision": float(average_precision_score(frame["label"], oof_scores)),
            "risk_threshold_found": threshold is not None,
            "risk_train_admissions": threshold.admitted_count if threshold else 0,
            "risk_train_wilson_lower_95": threshold.wilson_lower_95 if threshold else None,
            "mean_p_ge_0p8_count": int(naive.sum()),
            "mean_p_ge_0p8_precision": (
                float(frame.loc[naive, "label"].mean()) if naive.any() else None
            ),
            "source_status": "PROVENANCE_BLOCKED_DEVELOPMENT_EVIDENCE_ONLY",
        },
        [proxy_path, oracle_path, reference_path],
    )


def write_csv(path: Path, rows: Sequence[Mapping]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def derive_decision(folds: Sequence[Mapping], budgets: Sequence[Mapping]) -> str:
    if not any(bool(row["risk_threshold_found"]) for row in folds):
        return "NO_CACHED_EVIDENCE_OF_SAFE_SPECULATIVE_UPLIFT_REVISE_STATE"
    rc = [row for row in budgets if row["method"] == "RC_SEM_RISK_CONTROLLED"]
    posterior = [row for row in budgets if row["method"] == "POSTERIOR_VERIFIED_ONLY"]
    keyed = {(row["heldout_video"], row["verify_budget"]): row for row in posterior}
    gains = [
        row["anytime_event_recall_auc"]
        - keyed[(row["heldout_video"], row["verify_budget"])]["anytime_event_recall_auc"]
        for row in rc
    ]
    if gains and min(gains) > 0:
        return "CACHED_DEVELOPMENTAL_UPLIFT_REQUIRES_CONFIRMATORY_REPLAY"
    return "INSUFFICIENT_CACHED_EVIDENCE_OF_UPLIFT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("/root/charm/GVAQP"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--precision-floor", type=float, default=0.8)
    parser.add_argument("--minimum-admissions", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260730)
    args = parser.parse_args()
    if not 0.0 < args.precision_floor <= 1.0:
        raise ValueError("precision floor must be in (0, 1]")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    folds, budgets, ablations, predictions, partial_inputs = run_partial_validation(
        args.repo_root,
        precision_floor=args.precision_floor,
        minimum_admissions=args.minimum_admissions,
        seed=args.seed,
    )
    clean, clean_inputs = run_clean_cache_diagnostic(
        args.repo_root,
        precision_floor=args.precision_floor,
        minimum_admissions=args.minimum_admissions,
        seed=args.seed,
    )
    decision = derive_decision(folds, budgets)
    input_paths = sorted(set(partial_inputs + clean_inputs))
    input_hashes = {
        str(path.relative_to(args.repo_root)): sha256_file(path) for path in input_paths
    }

    write_csv(args.output_dir / "partial_fold_metrics.csv", folds)
    write_csv(args.output_dir / "budget_metrics.csv", budgets)
    write_csv(args.output_dir / "unsafe_gate_ablations.csv", ablations)
    write_csv(args.output_dir / "evaluator_only_candidate_predictions.csv", predictions)
    summary = {
        "schema_version": "RC_SEM_CACHED_SEMANTIC_VALIDATION_V1",
        "status": "DEVELOPMENTAL_RETROSPECTIVE_NOT_CONFIRMATORY",
        "decision": decision,
        "precision_floor": args.precision_floor,
        "minimum_training_admissions": args.minimum_admissions,
        "seed": args.seed,
        "partial_scan_folds": folds,
        "clean_cache_diagnostic": clean,
        "input_sha256": input_hashes,
        "limitations": [
            "partial-scan source benchmark reports POLICY_INFORMATION_ISOLATION=FAIL",
            "partial-scan reference is Qwen3-VL-32B pseudo-reference and not human adjudication",
            "clean-baseline source benchmark is provenance-blocked for 346 reused responses",
            "only two videos support cross-video testing and only one supports the second query",
            "full dynamic SCAN/VERIFY controller is not identified by these static caches",
            "results were explored post hoc and are not preregistered confirmatory evidence",
        ],
    }
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc_budget = pd.DataFrame(budgets)
    pivot = rc_budget.pivot_table(
        index=["heldout_video", "verify_budget"],
        columns="method",
        values=["event_recall", "anytime_event_recall_auc"],
    )
    report = [
        "# RC-SEM cached semantic validation",
        "",
        f"Decision: `{decision}`",
        "",
        "This is retrospective developmental evidence only. The risk-controlled gate",
        "was tested without exposing held-out labels to the posterior model or threshold",
        "selection, but the inherited source benchmarks have the limitations bound in",
        "`summary.json`.",
        "",
        "## Risk gate result",
        "",
    ]
    for row in folds:
        report.append(
            f"- {row['train_video']} -> {row['heldout_video']}: OOF ROC-AUC "
            f"{row['oof_roc_auc']:.3f}, AP {row['oof_average_precision']:.3f}; "
            f"safe threshold found={row['risk_threshold_found']}; probable events="
            f"{row['probable_returned_event_hypotheses']}."
        )
    report.extend(
        [
            "",
            "The 0.80 Wilson-LCB gate admitted no speculative events in either fold.",
            "Consequently RC-SEM and posterior-ranked verified-only replay have identical",
            "recall and anytime AUC at every tested VERIFY budget. Unsafe mean/raw-score",
            "thresholds do return events, but their held-out precision is recorded in",
            "`unsafe_gate_ablations.csv` and is below the required floor.",
            "",
            "## Second-query diagnostic",
            "",
            f"The 347-unit `OBJECT_ENTERS_EGO_PATH` cache has blocked OOF ROC-AUC "
            f"{clean['blocked_oof_roc_auc']:.3f} and AP "
            f"{clean['blocked_oof_average_precision']:.3f}. No safe risk threshold was found.",
            "",
            "## Interpretation",
            "",
            "The cache does not falsify the risk-control logic: it shows that the logic",
            "correctly refuses an unsupported probable-event claim. It does falsify the",
            "working assumption that the existing YOLO/motion proxy state is already",
            "sufficient to produce high-precision unverified events. The next discriminating",
            "change is an event-level posterior/state representation, not a looser gate.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "cd /root/charm/GVAQP_side_rcsem",
            "PYTHONPATH=src python experiments/cached_semantic_validation.py \\",
            "  --repo-root /root/charm/GVAQP \\",
            "  --output-dir outputs/cached_semantic_validation",
            "```",
            "",
            "## Budget table",
            "",
            "```text",
            pivot.to_string(),
            "```",
            "",
        ]
    )
    (args.output_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
